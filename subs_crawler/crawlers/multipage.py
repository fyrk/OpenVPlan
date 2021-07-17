import asyncio
import datetime
import logging
import time
from typing import Any, Dict, List, Optional, Tuple, Type, Union

import aiohttp

from subs_crawler.crawlers.base import BaseSubstitutionCrawler
from subs_crawler.parsers.base import AsyncBytesIOWrapper, BaseMultiPageSubstitutionParser, Stream
from subs_crawler.storage import SubstitutionStorage
from subs_crawler.utils import create_date_timestamp

_LOGGER = logging.getLogger("gawvertretung")


class MultiPageSubstitutionCrawler(BaseSubstitutionCrawler):
    _parser_class: Type[BaseMultiPageSubstitutionParser]

    def __init__(self, last_version_id: Optional[str],
                 parser_class: Type[BaseMultiPageSubstitutionParser], parser_options: Dict[str, Any],
                 url: str, site_load_count: int = 5, max_site_load_num: int = 99,
                 timeout_total: float = None, timeout_connect: float = None, timeout_sock_read: float = None,
                 timeout_sock_connect: float = None):
        super().__init__(last_version_id, parser_class, parser_options)
        self._url = url
        self._site_load_count = site_load_count
        self._max_site_load_num = max_site_load_num
        self._timeout = aiohttp.ClientTimeout(total=timeout_total, connect=timeout_connect, sock_read=timeout_sock_read,
                                              sock_connect=timeout_sock_connect)

        self._url_first_site = self._url.format(1)
        self._update_substitutions_lock = asyncio.Lock()

    async def _check_for_update(self, session: aiohttp.ClientSession) -> Tuple[bool, Optional[tuple]]:
        _LOGGER.debug(f"[multipage-crawler] Requesting first site ...")
        t1 = time.perf_counter_ns()
        async with session.get(self._url_first_site) as r:
            first_site = await r.read()
        t2 = time.perf_counter_ns()
        new_status, new_status_datetime = await self._parser_class.get_status(first_site)
        _LOGGER.debug(f"[multipage-crawler] Got answer in {t2 - t1}ns, status is {repr(new_status)} "
                      f"(old: {repr(self.last_version_id)})")
        return new_status != self.last_version_id, (new_status, new_status_datetime, first_site)

    async def update(self, session: aiohttp.ClientSession) \
            -> Tuple[bool, Optional[Dict[int, Dict[str, Union[str, List[str]]]]]]:
        if self._update_substitutions_lock.locked():
            _LOGGER.debug(f"[multipage-crawler] Substitutions are already being loaded")
            async with self._update_substitutions_lock:
                _LOGGER.debug(f"[multipage-crawler] Substitution loading finished")
                return False, None
        async with self._update_substitutions_lock:
            changed_substitutions, info = await self._check_for_update(session)
            if info is not None:
                new_status, new_status_datetime, first_site = info
            else:
                new_status, new_status_datetime, first_site = None, None, None
            affected_groups = None
            if changed_substitutions or self._storage is None:
                # if self._storage is None, this means substitutions haven't changed, but the server has been restarted,
                # so no substitutions are in memory
                t1 = time.perf_counter_ns()
                last_site_num, affected_groups = await self._load_data(session, new_status, new_status_datetime,
                                                                       first_site)
                self.last_version_id = new_status
                _LOGGER.debug(f"[multipage-crawler] Loaded data in {time.perf_counter_ns()-t1}ns")
            else:
                changed_substitutions = self._storage.remove_old_days()
            return changed_substitutions, affected_groups

    async def _load_data(self, session: aiohttp.ClientSession, status: str, status_datetime: datetime.datetime,
                         first_site: bytes) \
            -> Optional[Tuple[Optional[int], Optional[Dict[int, Dict[str, Union[str, List[str]]]]]]]:
        async def load_from_website(num):
            _LOGGER.debug(f"[multipage-crawler] {num} Requesting page")
            r = await session.get(self._url.format(num), timeout=self._timeout)
            _LOGGER.debug(f"[multipage-crawler] {num} Got {r.status}")
            if r.status == 200:
                await load_from_stream(num, r.content, r)

        async def load_from_stream(num, stream: Stream, request=None):
            nonlocal next_waiting_result, last_site_num
            _LOGGER.debug(f"[multipage-crawler] {num} Parsing")
            parser = self._parser_class(storage, current_timestamp, stream, num, **self._parser_options)
            # ignore PyTypeChecker because parser.parse is an async generator, not a coroutine
            # noinspection PyTypeChecker
            next_site = await parser.parse_next_site()
            if next_site == "001":
                _LOGGER.debug(f"[multipage-crawler] {num} is last site")
                last_site_num = num
                for l in loads[num-start_num+1:]:
                    l.cancel()
            results[num-start_num] = (parser, request)
            if next_waiting_result == num:
                index = next_waiting_result-start_num
                results_to_load = [(index+start_num, results[index])]
                results[index] = None
                next_waiting_result += 1
                index += 1
                while last_site_num is None or next_waiting_result <= last_site_num:
                    try:
                        if results[index] is not None:
                            results_to_load.append((index+start_num, results[index]))
                            results[index] = None
                            index += 1
                            next_waiting_result += 1
                        else:
                            break
                    except IndexError:
                        break

                async def complete_parse(parser, request):
                    try:
                        await parser.parse()
                        _LOGGER.debug(f"[multipage-crawler] {num} Finished parsing")
                    finally:
                        if request is not None:
                            request.close()

                await asyncio.gather(*(asyncio.ensure_future(complete_parse(parse, request))
                                     for num, (parse, request) in results_to_load))

        last_site_num = None
        current_timestamp = create_date_timestamp(datetime.datetime.now())
        storage = SubstitutionStorage(status, status_datetime)

        next_waiting_result = 1
        for start_num in range(1, self._max_site_load_num+1, self._site_load_count):
            end_num = start_num+self._site_load_count
            # load sites from start_num to end_num-1
            results: List[Optional[Tuple[BaseMultiPageSubstitutionParser, aiohttp.ClientResponse]]] = \
                [None for _ in range(self._site_load_count)]
            if start_num == 1 and first_site is not None:
                loads = ([asyncio.create_task(load_from_stream(1, AsyncBytesIOWrapper(first_site)), name="site1")] +
                         [asyncio.create_task(load_from_website(num), name="site" + str(num))
                          for num in range(start_num+1, end_num)])
            else:
                loads = [asyncio.create_task(load_from_website(num), name="site" + str(num))
                         for num in range(start_num, end_num)]
            _LOGGER.debug(f"[multipage-crawler] Loading pages {start_num} to {end_num-1}")
            try:
                done, pending = await asyncio.wait_for(asyncio.wait(loads, return_when=asyncio.FIRST_EXCEPTION),
                                                       timeout=1.0)
            except Exception as e:
                _LOGGER.error("[multipage-crawler] Got exception")
                for l in loads:
                    l.cancel()
                raise e
            for r in results:
                if r is not None:
                    r[1].close()
            for d in done:
                if not d.cancelled() and d.exception():
                    raise d.exception()
            if last_site_num is not None:
                new_affected_groups = storage.get_new_affected_groups(self._storage)
                self._storage = storage
                return last_site_num, new_affected_groups
        raise ValueError("Site loading limit (max_site_load_num={self._max_site_load_num}) reached")
