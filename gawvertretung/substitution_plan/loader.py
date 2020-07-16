import asyncio
import datetime
import io
import logging
import pickle
import time
from typing import Type, Union, Any, Optional, Callable, Tuple, List, Dict

import aiohttp
from aiohttp import client

from ..substitution_plan.parser import BaseSubstitutionParser, StudentSubstitutionParser, TeacherSubstitutionParser, \
    parse_next_site, SubstitutionsTooOldException, get_status_string, INCLUDE_OUTDATED_SUBSTITUTIONS
from ..substitution_plan.storage import StudentSubstitutionGroup, TeacherSubstitutionGroup, BaseSubstitutionGroup, \
    SubstitutionStorage
from ..substitution_plan.utils import create_date_timestamp


_LOGGER = logging.getLogger("gawvertretung")


class AsyncBytesIOWrapper(io.BytesIO):
    async def readline(self, **kwargs):
        return super().readline(**kwargs)

    async def readany(self):
        return super().read()


class BaseSubstitutionLoader:
    SITE_LOAD_COUNT = 5
    ENCODING = "iso-8859-1"
    _STORAGE_VERSION = b"\x00"

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
        self._storage: Optional[SubstitutionStorage] = None
        self._load_substitutions_lock = asyncio.Lock()

    @property
    def storage(self):
        return self._storage

    def serialize(self, filepath: str):
        # noinspection PyBroadException
        try:
            with open(filepath, "wb") as f:
                f.write(self._STORAGE_VERSION)
                pickle.dump(self._storage, f)
                pickle.dump(self._current_status_date, f)
            _LOGGER.debug(f"Wrote substitutions to '{filepath}'")
        except Exception:
            _LOGGER.exception(f"Could not serialize substitutions to '{filepath}'")

    def deserialize(self, filepath: str):
        # noinspection PyBroadException
        try:
            with open(filepath, "rb") as f:
                if f.read(1) != self._STORAGE_VERSION:
                    _LOGGER.warning(f"Could not deserialize substitutions from '{filepath}': "
                                    "Storage versions do not match")
                else:
                    self._storage = pickle.load(f)
                    self._current_status_date = pickle.load(f)
        except Exception:
            _LOGGER.exception(f"Could not deserialize substitutions from '{filepath}'")
        else:
            if self._storage is not None:
                _LOGGER.debug(f"Loaded substitutions from '{filepath}' with status '{self._storage.status}'")

    async def update(self, session: aiohttp.ClientSession) -> Tuple[bool, Optional[Dict[str, List[str]]]]:
        _LOGGER.debug(f"[{self._plan_name}] Requesting first site ...")
        t1 = time.perf_counter_ns()
        async with session.get(self._url_first_site) as r:
            first_site = await r.read()
        t2 = time.perf_counter_ns()
        new_status_string = get_status_string(first_site)
        old_status = self._storage.status if self._storage is not None else None
        _LOGGER.debug(f"[{self._plan_name}] Got answer in {t2 - t1}ns, status is {repr(new_status_string)} "
                      f"(old: {repr(old_status)})")
        changed_substitutions = False
        affected_groups = None
        if new_status_string != old_status:
            # status changed, load new data
            t1 = time.perf_counter_ns()
            res = await self._load_data(session, new_status_string, first_site)
            t2 = time.perf_counter_ns()
            if res is not None:
                # res is None when another request has already loaded new data
                last_site_num, affected_groups = res
                changed_substitutions = True
                if self.on_status_changed:
                    await self.on_status_changed(self._plan_name, new_status_string, last_site_num)
                _LOGGER.debug(f"[{self._plan_name}] Loaded data in {t2 - t1}ns")
        today = datetime.datetime.now()
        today_date = today.date()
        if today_date > self._current_status_date:
            self._current_status_date = today_date
            if not changed_substitutions and not INCLUDE_OUTDATED_SUBSTITUTIONS:
                _LOGGER.debug(f"[{self._plan_name}] Date changed, removing old substitutions")
                changed_substitutions = True
                self._storage.remove_old_days(create_date_timestamp(today))
        return changed_substitutions, affected_groups

    async def _load_data(self, session: aiohttp.ClientSession, status: str, first_site) -> \
            Optional[Tuple[Optional[int], Optional[Dict[str, List[str]]]]]:
        async def parse_site(num, request, stream):
            _LOGGER.debug(f"[{self._plan_name}] {num} Parsing")
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
                    _LOGGER.debug(f"[{self._plan_name}] {num} is outdated, skipping")
                    return
                except Exception:
                    _LOGGER.exception(f"[{self._plan_name}] {num} Exception while parsing")

        async def load_from_website(num):
            _LOGGER.debug(f"[{self._plan_name}] {num} Requesting page")
            r = await session.get(self._url.format(num), timeout=self.TIMEOUT)
            _LOGGER.debug(f"[{self._plan_name}] {num} Got {r.status}")
            if r.status == 200:
                await load_from_stream(num, r.content, r)

        async def load_from_stream(num, stream: Union[aiohttp.StreamReader, AsyncBytesIOWrapper], request=None):
            _LOGGER.debug(f"[{self._plan_name}] {num} Loading")
            nonlocal next_waiting_result, last_site_num
            next_site = await parse_next_site(stream)
            if b"001" == next_site:
                _LOGGER.debug(f"[{self._plan_name}] {num} is last site")
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
            _LOGGER.debug(f"[{self._plan_name}] Substitutions are already being loaded")
            async with self._load_substitutions_lock:
                _LOGGER.debug(f"[{self._plan_name}] Substitution loading finished")
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
                _LOGGER.debug(f"[{self._plan_name}] Loading pages {current_site} to {next_site - 1}")
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
                    return last_site_num, self._data_postprocessing(storage)
                current_site = next_site
            else:
                current_site = 1
                next_waiting_result = 1

            while True:
                next_site = current_site + self.SITE_LOAD_COUNT
                results = [None for _ in range(self.SITE_LOAD_COUNT)]

                loads = [asyncio.ensure_future(load_from_website(num)) for num in range(current_site, next_site)]
                _LOGGER.debug(f"[{self._plan_name}] Loading pages {current_site} to {next_site - 1}")
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
                    return last_site_num, self._data_postprocessing(storage)
                current_site = next_site

    def _data_postprocessing(self, substitution_storage: SubstitutionStorage) -> Dict[str, List[str]]:
        if self._storage:
            res = substitution_storage.mark_new_substitutions(self._storage)
        else:
            res = substitution_storage.get_all_affected_groups()
        self._storage = substitution_storage
        return res


class StudentSubstitutionLoader(BaseSubstitutionLoader):
    def __init__(self, url: str, plan_name: str):
        super().__init__(StudentSubstitutionParser, StudentSubstitutionGroup, url, plan_name)


class TeacherSubstitutionLoader(BaseSubstitutionLoader):
    def __init__(self, url: str, plan_name: str):
        super().__init__(TeacherSubstitutionParser, TeacherSubstitutionGroup, url, plan_name)
