import asyncio
import datetime
import io
import logging
from typing import Type, Union, Dict, Set, Any

import aiohttp

from substitution_plan.parser import BaseSubstitutionParser, StudentSubstitutionParser, TeacherSubstitutionParser, \
    parse_next_site, SubstitutionsTooOldException
from substitution_plan.storage import SubstitutionDay, StudentSubstitutionGroup, TeacherSubstitutionGroup, \
    BaseSubstitution
from substitution_plan.utils import create_date_timestamp
from website.stats import Stats

logger = logging.getLogger()


class AsyncBytesIOWrapper(io.BytesIO):
    async def readline(self, **kwargs):
        return super().readline(**kwargs)

    async def readany(self):
        return super().read()


class BaseSubstitutionLoader:
    SITE_LOAD_COUNT = 5
    ENCODING = "iso-8859-1"

    def __init__(self, substitutions_parser_class: Type[BaseSubstitutionParser], session: aiohttp.ClientSession,
                 plan_type: str, url: str, stats: Stats = None):
        self.substitutions_parser_factory = substitutions_parser_class
        self.session = session
        self.plan_type = plan_type
        self.url = url
        self.stats = stats

    async def load_data(self, old_days: Dict[int, Dict[Any, Set[BaseSubstitution]]], first_site=None):
        async def parse_site(num, request, stream, data, current_timestamp):
            logger.debug(f"{self.plan_type}: Parsing {num}")
            parser = self.substitutions_parser_factory(data, current_timestamp)
            while True:
                r = (await stream.readany()).decode(BaseSubstitutionLoader.ENCODING)
                if not r:
                    if request is not None:
                        request.close()
                    parser.close()
                    return
                try:
                    parser.feed(r)
                except SubstitutionsTooOldException:
                    return
                except Exception:
                    logger.exception(f"{self.plan_type}: Exception while parsing {num}")

        async def load_from_website(num):
            logger.debug(f"{self.plan_type}: Requesting {num}")
            r = await self.session.get(self.url.format(num))
            logger.debug(f"{self.plan_type}: Got {r.status} for {num}")
            if r.status == 200:
                await load_from_stream(num, r.content, r)

        async def load_from_stream(num, stream: Union[aiohttp.StreamReader, AsyncBytesIOWrapper], request=None):
            logger.debug(f"{self.plan_type}: Loading {num}")
            nonlocal next_waiting_result, last_site_num
            next_site = await parse_next_site(stream)
            if b"001" == next_site:
                logger.debug(f"{self.plan_type}: {num} is last site")
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
                logger.debug(f"{self.plan_type}: {num} ({index}, {next_waiting_result}, {last_site_num})")
                while last_site_num is None or next_waiting_result <= last_site_num:
                    try:
                        logger.debug(f"{self.plan_type}: {num} ({index}, {next_waiting_result}, {last_site_num})")
                        if results[index] is not None:
                            results_to_load.append((index+current_site, results[index]))
                            results[index] = None
                            index += 1
                            next_waiting_result += 1
                        else:
                            break
                    except IndexError:
                        break
                await asyncio.gather(*(asyncio.ensure_future(parse_site(num, request, stream, data, current_timestamp))
                                     for num, (request, stream) in results_to_load))
        last_site_num = None
        current_timestamp = create_date_timestamp(datetime.datetime.now())
        data = {}

        if first_site is not None:
            current_site = 1
            next_waiting_result = 1
            next_site = current_site + self.SITE_LOAD_COUNT
            results = [None for _ in range(self.SITE_LOAD_COUNT)]
            loads = [asyncio.ensure_future(load_from_stream(1, AsyncBytesIOWrapper(first_site)))] + \
                    [asyncio.ensure_future(load_from_website(num)) for num in range(current_site+1, next_site)]

            await asyncio.wait(loads)
            for r in results[next_waiting_result:]:
                if r is not None and r[0] is not None:
                    r[0].close()
            if last_site_num is not None:
                if self.stats is not None:
                    self.stats.add_last_site(last_site_num)
                return self._data_postprocessing(old_days, data)
            current_site = next_site
        else:
            current_site = 1
            next_waiting_result = 1

        while True:
            next_site = current_site + self.SITE_LOAD_COUNT
            results = [None for _ in range(self.SITE_LOAD_COUNT)]

            loads = [asyncio.ensure_future(load_from_website(num)) for num in range(current_site, next_site)]

            await asyncio.wait(loads)
            for r in results[next_waiting_result:]:
                if r is not None:
                    r[0].close()
            if last_site_num is not None:
                if self.stats is not None:
                    self.stats.add_last_site(last_site_num)
                logger.debug(self.plan_type + " results: " + str(results))
                return self._data_postprocessing(old_days, data)
            current_site = next_site

    def _data_postprocessing(self, old_days: Dict[int, Dict[Any, Set[BaseSubstitution]]], data: dict):
        days = sorted(
            SubstitutionDay(
                timestamp,
                day["day_name"],
                day["date"],
                day["week"],
                day["news"],
                day["info"],
                self._sort_substitutions(day["substitutions"])
            )
            for timestamp, day in data.items()
        )
        for day in days:
            try:
                day.mark_new_substitutions(old_days[day.timestamp])
            except KeyError:
                pass
        return days

    def _sort_substitutions(self, substitutions: dict):
        raise NotImplementedError


class StudentSubstitutionLoader(BaseSubstitutionLoader):
    def __init__(self, session: aiohttp.ClientSession, plan_type: str, url: str, stats: Stats = None):
        super().__init__(StudentSubstitutionParser, session, plan_type, url, stats)

    def _sort_substitutions(self, substitutions: dict):
        return sorted(StudentSubstitutionGroup(group_name, substitutions)
                      for group_name, substitutions in substitutions.items())


class TeacherSubstitutionLoader(BaseSubstitutionLoader):
    def __init__(self, session: aiohttp.ClientSession, plan_type: str, url: str, stats: Stats = None):
        super().__init__(TeacherSubstitutionParser, session, plan_type, url, stats)

    def _sort_substitutions(self, substitutions: dict):
        return sorted(TeacherSubstitutionGroup(group_name, substitutions)
                      for group_name, substitutions in substitutions.items())
