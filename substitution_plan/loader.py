import asyncio
import datetime
import io
import logging
import time
from typing import Type, Union, Any, Optional, Callable

import aiohttp
from aiohttp import client

from substitution_plan.parser import BaseSubstitutionParser, StudentSubstitutionParser, TeacherSubstitutionParser, \
    parse_next_site, SubstitutionsTooOldException, get_status_string, INCLUDE_OUTDATED_SUBSTITUTIONS
from substitution_plan.storage import StudentSubstitutionGroup, TeacherSubstitutionGroup, BaseSubstitutionGroup, \
    SubstitutionStorage
from substitution_plan.utils import create_date_timestamp


logger = logging.getLogger("gawvertretung")


class AsyncBytesIOWrapper(io.BytesIO):
    async def readline(self, **kwargs):
        return super().readline(**kwargs)

    async def readany(self):
        return super().read()


class BaseSubstitutionLoader:
    SITE_LOAD_COUNT = 5
    ENCODING = "iso-8859-1"

    TIMEOUT = client.ClientTimeout(1)

    def __init__(self, substitutions_parser_factory: Type[BaseSubstitutionParser],
                 substitution_group_factory: Type[BaseSubstitutionGroup], url: str, plan_name: str):
        self._substitutions_parser_factory = substitutions_parser_factory
        self._substitution_group_factory = substitution_group_factory
        self._url = url
        self._plan_name = plan_name
        self.on_status_changed: Optional[Callable[[str, str, int], Any]] = None
        self.on_new_substitution_storage: Optional[Callable[[SubstitutionStorage], Any]] = None

        self._url_first_site = self._url.format(1)
        self._current_status_date = datetime.datetime.now().date()
        self._substitution_storage: Optional[SubstitutionStorage] = None
        self._load_substitutions_lock = asyncio.Lock()

    @property
    def storage(self) -> SubstitutionStorage:
        return self._substitution_storage

    async def update(self, session: aiohttp.ClientSession) -> bool:
        logger.debug(f"[{self._plan_name}] Requesting first site ...")
        t1 = time.perf_counter_ns()
        async with session.get(self._url_first_site) as r:
            first_site = await r.read()
        t2 = time.perf_counter_ns()
        new_status_string = get_status_string(first_site)
        old_status = self._substitution_storage.status if self._substitution_storage is not None else None
        logger.debug(f"[{self._plan_name}] Got answer in {t2 - t1}ns, status is {repr(new_status_string)}, "
                     f"old: {repr(old_status)}")
        changed_substitutions = False
        if new_status_string != old_status:
            # status changed, load new data
            t1 = time.perf_counter_ns()
            last_site_num = await self._load_data(session, new_status_string, first_site)
            t2 = time.perf_counter_ns()
            if last_site_num is not None:
                # last_site_num is None when another request has already loaded new data
                changed_substitutions = True
                if self.on_status_changed:
                    await self.on_status_changed(self._plan_name, new_status_string, last_site_num)
                logger.debug(f"[{self._plan_name}] Loaded data in {t2-t1}ns")
        today = datetime.datetime.now()
        today_date = today.date()
        if today_date > self._current_status_date:
            self._current_status_date = today_date
            if not changed_substitutions and not INCLUDE_OUTDATED_SUBSTITUTIONS:
                changed_substitutions = True
                logger.debug(f"[{self._plan_name}] Date changed, recreating sites")
                self._substitution_storage.remove_old_days(create_date_timestamp(today))
        return changed_substitutions

    async def _load_data(self, session: aiohttp.ClientSession, status: str, first_site) -> Optional[int]:
        async def parse_site(num, request, stream):
            logger.debug(f"[{self._plan_name}] Parsing {num}")
            parser = self._substitutions_parser_factory(storage, current_timestamp)
            while True:
                r = (await stream.readany()).decode(BaseSubstitutionLoader.ENCODING)
                if not r:
                    if request is not None:
                        request.close()
                    parser.close()
                    return
                # noinspection PyBroadException
                try:
                    parser.feed(r)
                except SubstitutionsTooOldException:
                    return
                except Exception:
                    logger.exception(f"[{self._plan_name}] Exception while parsing {num}")

        async def load_from_website(num):
            logger.debug(f"[{self._plan_name}] Requesting {num}")
            r = await session.get(self._url.format(num), timeout=self.TIMEOUT)
            logger.debug(f"[{self._plan_name}] Got {r.status} for {num}")
            if r.status == 200:
                await load_from_stream(num, r.content, r)

        async def load_from_stream(num, stream: Union[aiohttp.StreamReader, AsyncBytesIOWrapper], request=None):
            logger.debug(f"[{self._plan_name}] Loading {num}")
            nonlocal next_waiting_result, last_site_num
            next_site = await parse_next_site(stream)
            if b"001" == next_site:
                logger.debug(f"[{self._plan_name}] {num} is last site")
                last_site_num = num
                for l in loads[num-current_site+1:]:
                    l.cancel()
            results[num-current_site] = (request, stream)
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
                await asyncio.gather(*(asyncio.ensure_future(parse_site(num, request, stream))
                                     for num, (request, stream) in results_to_load))

        if self._load_substitutions_lock.locked():
            logger.debug(f"[{self._plan_name}] Substitutions are already being loaded")
            async with self._load_substitutions_lock:
                logger.debug(f"[{self._plan_name}] Substitution loading finished")
                return None
        async with self._load_substitutions_lock:
            last_site_num = None
            current_timestamp = create_date_timestamp(datetime.datetime.now())
            storage = SubstitutionStorage(status)

            if first_site is not None:
                current_site = 1
                next_waiting_result = 1
                next_site = current_site + self.SITE_LOAD_COUNT
                results = [None for _ in range(self.SITE_LOAD_COUNT)]
                loads = [asyncio.ensure_future(load_from_stream(1, AsyncBytesIOWrapper(first_site)))] + \
                        [asyncio.ensure_future(load_from_website(num)) for num in range(current_site+1, next_site)]
                logger.info("loading " + str(current_site) + " " + str(next_site))
                try:
                    await asyncio.wait_for(asyncio.wait(loads), timeout=1.0)
                except asyncio.TimeoutError as e:
                    for l in loads:
                        l.cancel()
                    raise e
                for r in results[next_waiting_result:]:
                    if r is not None and r[0] is not None:
                        r[0].close()
                if last_site_num is not None:
                    self._data_postprocessing(storage)
                    return last_site_num
                current_site = next_site
            else:
                current_site = 1
                next_waiting_result = 1

            while True:
                next_site = current_site + self.SITE_LOAD_COUNT
                results = [None for _ in range(self.SITE_LOAD_COUNT)]

                loads = [asyncio.ensure_future(load_from_website(num)) for num in range(current_site, next_site)]
                logger.info("loading " + str(current_site) + " " + str(next_site))
                try:
                    await asyncio.wait_for(asyncio.wait(loads), timeout=1.0)
                except asyncio.TimeoutError as e:
                    for l in loads:
                        l.cancel()
                    raise e
                for r in results[next_waiting_result:]:
                    if r is not None:
                        r[0].close()
                if last_site_num is not None:
                    self._data_postprocessing(storage)
                    return last_site_num
                current_site = next_site

    def _data_postprocessing(self, substitution_storage: SubstitutionStorage):
        if self._substitution_storage:
            substitution_storage.mark_new_substitutions(self._substitution_storage)
        self._substitution_storage = substitution_storage


class StudentSubstitutionLoader(BaseSubstitutionLoader):
    def __init__(self, url: str, plan_name: str):
        super().__init__(StudentSubstitutionParser, StudentSubstitutionGroup, url, plan_name)


class TeacherSubstitutionLoader(BaseSubstitutionLoader):
    def __init__(self, url: str, plan_name: str):
        super().__init__(TeacherSubstitutionParser, TeacherSubstitutionGroup, url, plan_name)
