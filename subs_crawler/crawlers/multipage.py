import asyncio
import datetime
import logging
import time
from typing import Any, AsyncGenerator, Callable, Dict, List, Optional, Tuple, Type, Union

import aiohttp
from aiohttp import client

from subs_crawler.crawlers.base import BaseSubstitutionCrawler
from subs_crawler.parsers.base import AsyncBytesIOWrapper, BaseMultiPageSubstitutionParser, Stream
from subs_crawler.storage import SubstitutionStorage
from subs_crawler.utils import create_date_timestamp

_LOGGER = logging.getLogger("gawvertretung")


class MultiPageSubstitutionCrawler(BaseSubstitutionCrawler):
    SITE_LOAD_COUNT = 5

    TIMEOUT = client.ClientTimeout(1)

    def __init__(self, parser_class: Type[BaseMultiPageSubstitutionParser], parser_options: Dict[str, Any], url: str,
                 timeout_total: float = None, timeout_connect: float = None, timeout_sock_read: float = None,
                 timeout_sock_connect: float = None):
        self._parser_class = parser_class
        self._parser_options = parser_options
        self._url = url
        self._timeout = client.ClientTimeout(total=timeout_total, connect=timeout_connect, sock_read=timeout_sock_read,
                                             sock_connect=timeout_sock_connect)
        self.on_status_changed: Optional[Callable[[str, int], Any]] = None
        self.on_new_substitution_storage: Optional[Callable[[SubstitutionStorage], Any]] = None

        self._url_first_site = self._url.format(1)
        self._current_status_date = datetime.datetime.now().date()
        self._storage: Optional[SubstitutionStorage] = None
        self._load_substitutions_lock = asyncio.Lock()

    @property
    def storage(self):
        return self._storage

    async def update(self, session: aiohttp.ClientSession) \
            -> Tuple[bool, Optional[Dict[int, Dict[str, Union[str, List[str]]]]]]:
        _LOGGER.debug(f"Requesting first site ...")
        t1 = time.perf_counter_ns()
        async with session.get(self._url_first_site) as r:
            first_site = await r.read()
        t2 = time.perf_counter_ns()
        new_status_string, new_status_datetime = await self._parser_class.get_status(first_site)
        old_status = self._storage.status if self._storage is not None else None
        _LOGGER.debug(f"Got answer in {t2 - t1}ns, status is {repr(new_status_string)} (old: {repr(old_status)})")
        affected_groups = None
        if new_status_string != old_status:
            # status changed, load new data
            t1 = time.perf_counter_ns()
            if (res := await self._load_data(session, new_status_string, new_status_datetime, first_site)) is None:
                # res is None when another request has already loaded new data
                return False, None
            t2 = time.perf_counter_ns()
            last_site_num, affected_groups = res
            changed_substitutions = True
            if self.on_status_changed:
                await self.on_status_changed(new_status_string, last_site_num)
            _LOGGER.debug(f"Loaded data in {t2 - t1}ns")
        else:
            changed_substitutions = self._storage.remove_old_days()
        return changed_substitutions, affected_groups

    async def _load_data(self, session: aiohttp.ClientSession, status: str, status_datetime: datetime.datetime,
                         first_site) -> \
            Optional[Tuple[Optional[int], Optional[Dict[int, Dict[str, Union[str, List[str]]]]]]]:
        async def load_from_website(num):
            _LOGGER.debug(f"{num} Requesting page")
            r = await session.get(self._url.format(num), timeout=self.TIMEOUT)
            _LOGGER.debug(f"{num} Got {r.status}")
            if r.status == 200:
                await load_from_stream(num, r.content, r)

        async def load_from_stream(num, stream: Stream, request=None):
            nonlocal next_waiting_result, last_site_num
            _LOGGER.debug(f"{num} Loading")
            parser = self._parser_class(storage, current_timestamp, stream, num, **self._parser_options)
            # ignore PyTypeChecker because parser.parse is an async generator, not a coroutine
            # noinspection PyTypeChecker
            next_site: AsyncGenerator = await parser.parse_next_site()
            if b"001" == next_site:
                _LOGGER.debug(f"{num} is last site")
                last_site_num = num
                for l in loads[num-current_site+1:]:
                    l.cancel()
            results[num-current_site] = (parser, request)
            if next_waiting_result == num:
                index = next_waiting_result-current_site
                results_to_load = [(index+current_site, results[index])]
                results[index] = None
                next_waiting_result += 1
                index += 1
                while last_site_num is None or next_waiting_result <= last_site_num:
                    try:
                        if results[index] is not None:
                            results_to_load.append((index+current_site, results[index]))
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
                    finally:
                        if request is not None:
                            request.close()
                await asyncio.gather(*(asyncio.ensure_future(complete_parse(parse, request))
                                     for num, (parse, request) in results_to_load))
                _LOGGER.info(f"Finished load_from_stream {num} (if)")
            _LOGGER.info(f"Finished load_from_stream {num}")

        if self._load_substitutions_lock.locked():
            _LOGGER.debug(f"Substitutions are already being loaded")
            async with self._load_substitutions_lock:
                _LOGGER.debug(f"Substitution loading finished")
                return None
        async with self._load_substitutions_lock:
            last_site_num = None
            current_timestamp = create_date_timestamp(datetime.datetime.now())
            storage = SubstitutionStorage(status, status_datetime)

            current_site = 1
            next_waiting_result = 1
            while True:
                next_site = current_site + self.SITE_LOAD_COUNT
                results: List[Optional[Tuple[BaseMultiPageSubstitutionParser, aiohttp.ClientResponse]]] = \
                    [None for _ in range(self.SITE_LOAD_COUNT)]
                if current_site == 1 and first_site is not None:
                    loads = ([asyncio.create_task(load_from_stream(1, AsyncBytesIOWrapper(first_site)), name="site1")] +
                             [asyncio.create_task(load_from_website(num), name="site" + str(num))
                              for num in range(current_site+1, next_site)])
                else:
                    loads = [asyncio.create_task(load_from_website(num), name="site" + str(num))
                             for num in range(current_site, next_site)]
                _LOGGER.debug(f"Loading pages {current_site} to {next_site - 1}")
                try:
                    await asyncio.wait_for(asyncio.wait(loads, return_when=asyncio.FIRST_EXCEPTION), timeout=1.0)
                except Exception as e:
                    _LOGGER.exception("Got exception")
                    for l in loads:
                        l.cancel()
                    raise e
                _LOGGER.info("Finished gather")
                for r in results:
                    if r is not None:
                        r[1].close()
                if last_site_num is not None:
                    new_affected_groups = storage.get_new_affected_groups(self._storage)
                    _LOGGER.info("Set _storage")
                    self._storage = storage
                    return last_site_num, new_affected_groups
                current_site = next_site
