import asyncio
import datetime
import logging
import time
from typing import Any, Callable, Dict, List, Optional, Tuple, Type, Union

import aiohttp

from subs_crawler.crawlers.base import BaseSubstitutionCrawler
from subs_crawler.parsers.base import BaseMultiPageSubstitutionParser
from subs_crawler.storage import SubstitutionStorage
from subs_crawler.utils import create_date_timestamp

_LOGGER = logging.getLogger("gawvertretung")


class DsbmobileSubstitutionCrawler(BaseSubstitutionCrawler):
    BASE_URL = "https://mobileapi.dsbcontrol.de"

    _parser_class: Type[BaseMultiPageSubstitutionParser]

    def __init__(self, parser_class: Type[BaseMultiPageSubstitutionParser], parser_options: Dict[str, Any],
                 username: str, password: str, timeout_total: float = None, timeout_connect: float = None,
                 timeout_sock_read: float = None, timeout_sock_connect: float = None):
        super().__init__(parser_class, parser_options)
        self._username = username
        self._password = password
        self._timeout = aiohttp.ClientTimeout(total=timeout_total, connect=timeout_connect, sock_read=timeout_sock_read,
                                              sock_connect=timeout_sock_connect)

        self.on_status_changed: Optional[Callable[[str, int], Any]] = None
        self._load_substitutions_lock = asyncio.Lock()

    async def update(self, session: aiohttp.ClientSession) \
            -> Tuple[bool, Optional[Dict[int, Dict[str, Union[str, List[str]]]]]]:
        # the following uses information from https://github.com/sn0wmanmj/pydsb (MIT license)
        _LOGGER.debug("[dsbmobile-crawler] Requesting token")
        t1 = time.perf_counter_ns()
        r = await session.get(self.BASE_URL + "/authid?bundleid=de.heinekingmedia.dsbmobile"
                               "&appversion=35&osversion=22&pushid",
                               params={"user": self._username, "password": self._password})
        r.raise_for_status()
        token = await r.json()
        r.close()
        if type(token) != str or len(token) != 36:
            raise ValueError(f"Unexpected response: {r.status} {token}")
        _LOGGER.debug("[dsbmobile-crawler] Requesting substitution plan list")
        r = await session.get(self.BASE_URL + "/dsbtimetables", params={"authid": token})
        r.raise_for_status()
        data = (await r.json())[0]
        r.close()
        status = data["Date"]
        status_datetime = datetime.datetime.strptime(status, "%d.%m.%Y %H:%M")
        old_status = self._storage.status if self._storage is not None else None
        t2 = time.perf_counter_ns()
        _LOGGER.debug(f"[dsbmobile-crawler] Got answer in {t2 - t1}ns, "
                      f"status is {repr(status)} (old: {repr(old_status)})")
        affected_groups = None
        if status != old_status:
            # status changed, load new data
            t1 = time.perf_counter_ns()
            if (res := await self._load_data(session, status, status_datetime, data)) is None:
                # res is None when another request has already loaded new data
                return False, None
            t2 = time.perf_counter_ns()
            last_site_num, affected_groups = res
            changed_substitutions = True
            if self.on_status_changed:
                await self.on_status_changed(status, last_site_num)
            _LOGGER.debug(f"[dsbmobile-crawler] Loaded data in {t2 - t1}ns")
        else:
            changed_substitutions = self._storage.remove_old_days()
        return changed_substitutions, affected_groups

    async def _load_data(self, session: aiohttp.ClientSession, status: str, status_datetime: datetime.datetime,
                         data: dict) -> \
            Optional[Tuple[Optional[int], Optional[Dict[int, Dict[str, Union[str, List[str]]]]]]]:
        async def load_data(url, num):
            _LOGGER.debug(f"[multipage-crawler] {num} Sending request")
            r = await session.get(url, timeout=self._timeout)
            _LOGGER.debug(f"[multipage-crawler] {num} Got {r.status}")
            if r.status == 200:
                _LOGGER.debug(f"[multipage-crawler] {num} Parsing")
                await self._parser_class(storage, current_timestamp, r.content, num, **self._parser_options).parse()
                _LOGGER.debug(f"[multipage-crawler] {num} Finished parsing")

        if self._load_substitutions_lock.locked():
            _LOGGER.debug(f"[dsbmobile-crawler] Substitutions are already being loaded")
            async with self._load_substitutions_lock:
                _LOGGER.debug(f"[dsbmobile-crawler] Substitution loading finished")
                return None
        async with self._load_substitutions_lock:
            _LOGGER.debug("[dsbmobile-crawler] Loading substitution data...")
            current_timestamp = create_date_timestamp(datetime.datetime.now())
            storage = SubstitutionStorage(status, status_datetime)
            tasks = [asyncio.create_task(load_data(url, num))
                     for num, url in enumerate((site["Detail"] for site in data["Childs"]), 1)]
            try:
                done, pending = await asyncio.wait_for(asyncio.wait(tasks, return_when=asyncio.FIRST_EXCEPTION),
                                                       timeout=2.0)
                for t in tasks:
                    t.cancel()
                has_exception = False
                for t in done:
                    if t.exception():
                        _LOGGER.exception("Exception while parsing", exc_info=t.exception())
                        has_exception = True
                if has_exception:
                    raise ValueError("Could not complete parsing")
            except Exception as e:
                _LOGGER.error("[dsbmobile-crawler] Got exception")
                for t in tasks:
                    t.cancel()
                raise e
            new_affected_groups = storage.get_new_affected_groups(self._storage)
            self._storage = storage
            return len(data["Childs"]), new_affected_groups
