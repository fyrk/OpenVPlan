
#  OpenVPlan
#  Copyright (C) 2019-2021  Florian Rädiker
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU Affero General Public License as published
#  by the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU Affero General Public License for more details.
#
#  You should have received a copy of the GNU Affero General Public License
#  along with this program.  If not, see <https://www.gnu.org/licenses/>.

import asyncio
import datetime
from html.parser import HTMLParser
import json
import logging
from re import T
import time
from typing import Tuple, Optional, Dict, Union, List

import aiohttp

from ..crawlers.base import BaseSubstitutionCrawler
from ..storage import Substitution, SubstitutionDay, SubstitutionGroup, SubstitutionStorage
from ..utils import get_lesson_num, simplify_class_name


_LOGGER = logging.getLogger("openvplan")


_ALLOWED_FORMATTING_TAGS = ("b", "code", "em", "i", "kbd", "mark", "s", "small", "strong", "sub", "sub", "u",
                            "big", "blink", "center", "strike", "tt")
def _strip_html(html: str, allowed_tags=_ALLOWED_FORMATTING_TAGS) -> str:
    """Remove HTML tags in a string"""
    res = ""
    class HTMLStripper(HTMLParser):
        def handle_data(self, data: str):
            nonlocal res
            res += data
        def handle_starttag(self, tag: str, attrs: List[Tuple[str, Union[str, None]]]):
            nonlocal res
            if allowed_tags and tag in allowed_tags:
                res += "<" + tag + ">"
        def handle_endtag(self, tag: str):
            nonlocal res
            if allowed_tags and tag in allowed_tags:
                res += "<" + tag + "/>"
    HTMLStripper().feed(html)
    return res


class WebuntisCrawler(BaseSubstitutionCrawler):
    DEFAULT_FORMAT = {
        "strikethrough": True,
        "mergeBlocks": True,
        "showOnlyFutureSub": True,
        "showBreakSupervisions": True,
        "showTeacher": True,
        "showClass": True,
        "showHour": True,
        "showInfo": True,
        "showRoom": True,
        "showSubject": True,
        "groupBy": 1,
        "hideAbsent": False,
        "departmentIds": [],
        "departmentElementType": -1,
        "hideCancelWithSubstitution": False,
        "hideCancelCausedByEvent": False,
        "showTime": False,
        "showSubstText": True,
        "showAbsentElements": [1],
        "showAffectedElements": [1],
        "showUnitTime": True,
        "showMessages": True,
        "showStudentgroup": False,
        "enableSubstitutionFrom": False,
        "showSubstitutionFrom": 0,
        "showTeacherOnEvent": False,
        "showAbsentTeacher": True,
        "strikethroughAbsentTeacher": False,
        "activityTypeIds": [],
        "showEvent": True,
        "showCancel": True,
        "showOnlyCancel": False,
        "showSubstTypeColor": False,
        "showExamSupervision": True,
        "showUnheraldedExams": True
    }

    FORMAT_LOAD_INTERVAL = 5*60  # every 5 minutes

    def __init__(self, last_version_id,
                 url: str, school_name: str, format_name: str, max_day_count: int = 5, reorder: List[int] = None, format_overrides: Dict[str, str] = None,
                 lesson_column: int = None, group_name_is_class: bool = True, affected_groups_columns: List[int] = None, class_columns: List[int] = None,
                 timeout_total: float = None, timeout_connect: float = None, timeout_sock_read: float = None,
                 timeout_sock_connect: float = None):
        super().__init__(last_version_id)
        self._url = url
        self._school_name = school_name
        self._format_name = format_name
        self._max_day_count = max_day_count
        self._reorder = reorder
        self._format_overrides = format_overrides
        self._lesson_column = lesson_column
        self._group_name_is_class = group_name_is_class
        self._affected_groups_columns = affected_groups_columns
        self._class_columns = class_columns

        self._format: Optional[dict] = None
        self._last_format_load_time = 0

        self._timeout = aiohttp.ClientTimeout(total=timeout_total, connect=timeout_connect, sock_read=timeout_sock_read,
                                              sock_connect=timeout_sock_connect)

        self._update_substitutions_lock = asyncio.Lock()
        self._parse_data_lock = asyncio.Lock()

    async def update(self, session: aiohttp.ClientSession) \
            -> Tuple[bool, Optional[Dict[datetime.date, Dict[str, Union[str, List[str]]]]]]:
        if self._update_substitutions_lock.locked():
            _LOGGER.debug(f"[webuntis-crawler] Substitutions are already being loaded")
            async with self._update_substitutions_lock:
                _LOGGER.debug(f"[webuntis-crawler] Substitution loading finished")
                return False, None
        async with self._update_substitutions_lock:
            t1 = time.perf_counter_ns()
            _LOGGER.info(f"[webuntis-crawler] last_version_id: {self.last_version_id!r}")
            storage = SubstitutionStorage(None, None)
            today = datetime.date.today()

            await self._load_format(session)

            tasks = [asyncio.ensure_future(self._load_data(session, storage, today, i))
                     for i in range(self._max_day_count)]
            try:
                await asyncio.gather(*tasks)
            except Exception as e:
                for t in tasks:
                    t.cancel()
                raise e from None

            storage.status = tasks[0].result()
            storage.status_datetime = datetime.datetime.strptime(storage.status, "%d.%m.%Y %H:%M:%S")

            if storage.status == (self.last_version_id and self.last_version_id.get("status")):
                # substitutions have not changed
                if self._storage is None:
                    # if self._storage is None, this means substitutions haven't necessarily changed,
                    # but this is the first time they are updated since the server started
                    reload_required = True
                    self._storage = storage
                else:
                    reload_required = self._storage.remove_old_days()
                affected_groups = None
            else:
                # substitutions have changed
                affected_groups = storage.get_new_affected_groups(self._storage)
                self.last_version_id = {"status": storage.status}
                reload_required = True
                self._storage = storage

            if not all(t.result() == storage.status for t in tasks):
                _LOGGER.warning(f"[webuntis-crawler] Different status for formats: {[t.result() for t in tasks]}")
                reload_required = True

            t = time.perf_counter_ns() - t1
            _LOGGER.debug(f"[webuntis-crawler] Loaded data in {t}ns (~{t/1e9:.2f}s); affected groups: {affected_groups!r}")
            return reload_required, affected_groups
    
    async def _load_format(self, session: aiohttp.ClientSession):
        t1 = time.perf_counter_ns()
        now = time.time()
        if not self._format or now-self._last_format_load_time > self.FORMAT_LOAD_INTERVAL or True:
            _LOGGER.info("[webuntis-crawler] Updating format ...")
            async with session.post(
                    self._url+"/WebUntis/monitor/substitution/format",
                    params={"school": self._school_name},
                    json={
                        "schoolName": self._school_name,
                        "formatName": self._format_name
                    },
                    allow_redirects=False) as r:
                r.raise_for_status()
                try:
                    data = await r.json()
                except Exception as e:
                    _LOGGER.error(f"[webuntis-crawler] format: Failed to parse response: {r._body}")
                    raise e from None
            try:
                data: dict = data["payload"]
                new_format = self.DEFAULT_FORMAT.copy()
                not_existing = []
                for key in new_format:
                    if key in data:
                        new_format[key] = data[key]
                    else:
                        not_existing.append(key)
                if self._format_overrides:
                    new_format.update(self._format_overrides)
                if new_format != self._format:
                    for key in not_existing:
                        _LOGGER.debug(f"[webuntis-crawler] key {key!r} from default format not found in format response")
                    _LOGGER.info(f"[webuntis-crawler] NEW FORMAT: {json.dumps(new_format)}")
                self._format = new_format
            except Exception as e:
                _LOGGER.error(f"[webuntis-crawler] format: Failed to parse data: {data}")
                raise e from None
            t = time.perf_counter_ns() - t1
            _LOGGER.debug(f"[webuntis-crawler] Updating format finished in {t}ns (~{t/1e9:.2f}s)")
            self._last_format_load_time = now

    async def _load_data(self, session: aiohttp.ClientSession, storage: SubstitutionStorage, date: datetime.date, date_offset: int) -> str:
        _LOGGER.debug(f"[webuntis-crawler] {date_offset} loading ...")
        t1 = time.perf_counter_ns()
        def log_finish(msg):
            t = time.perf_counter_ns() - t1
            _LOGGER.debug(f"[webuntis-crawler] {date_offset} Finished in {t}ns (~{t/1e9:.2f}s): {msg}")

        async with session.post(
                self._url+"/WebUntis/monitor/substitution/data",
                params={"school": self._school_name},
                json=self._format | {
                    "schoolName": self._school_name,
                    "formatName": self._format_name,
                    "date": int(date.strftime("%Y%m%d")),
                    "dateOffset": date_offset
                }, 
                allow_redirects=False) as r:
            r.raise_for_status()
            try:
                data = await r.json()
            except Exception as e:
                _LOGGER.error(f"[webuntis-crawler] {date_offset} Failed to parse response: {r._body}")
                raise e from None
        try:
            data: dict = data["payload"]
            if data["importInProgress"] is not None:
                _LOGGER.warning(f"[webuntis-crawler] \"importInProgress\" is {data['importInProgress']!r}")

            last_update = data["lastUpdate"]
            date = datetime.datetime.strptime(str(data["date"]), "%Y%m%d").date()                        
            if date is None:
                # date is None when there are no substitutions
                return last_update
            
            _LOGGER.debug(f"[webuntis-crawler] {date_offset} lastUpdate: {last_update!r}; date: {date}; name: {data['weekDay']}")
            if (self.last_version_id and self.last_version_id.get("status")) == last_update and self._storage is not None:
                log_finish("no new update and storage exists")
                return last_update

            if date < datetime.date.today():
                log_finish(f"day {data['date']!r} is in the past")
                return last_update

            async with self._parse_data_lock:  # prevent race conditions in storage
                if storage.has_day(date):
                    day = storage.get_day(date)
                else:
                    day = SubstitutionDay(date=date, name=data["weekDay"], datestr=date.strftime("%d.%m.%Y"), week=None)
                    storage.add_day(day)
                
                # SUBSTITUTIONS
                for row in data["rows"]:
                    subs_data = [_strip_html(s, None) for s in row["data"]]
                    if self._lesson_column is not None:
                        lesson_num = get_lesson_num(subs_data[self._lesson_column])
                    else:
                        lesson_num = None
                    if self._class_columns:
                        for column in self._class_columns:
                            subs_data[column] = simplify_class_name(subs_data[column])
                    if self._reorder:
                        subs_data = tuple(subs_data[i] for i in self._reorder)
                    substitution = Substitution(
                        data=subs_data,
                        lesson_num=lesson_num,
                        name_is_class=self._group_name_is_class,
                        affected_groups_columns=self._affected_groups_columns
                    )
                    group_id = (row["group"], False)  # not striked
                    if (group := day.get_group(group_id)) is not None:
                        group.substitutions.append(substitution)
                    else:
                        subs_group = SubstitutionGroup(group_id[0], group_id[1], [substitution], self._group_name_is_class)
                        day.add_group(subs_group)


                # ABSENCES
                absent_classes = []
                absent_teachers = []
                for e in data["absentElements"]:
                    """Examples for e:
                    {
                        "elementType": 2,
                        "elementId": 4,
                        "elementName": "ABC",
                        "startUnit": null,
                        "endUnit": null,
                        "absences": [
                        {
                            "type": "ALL_DAY",
                            "startTime": 0,
                            "endTime": 2359,
                            "isEvent": false,
                            "startUnit": "0",
                            "endUnit": "0"
                        }
                        ]
                    },
                    {
                        "elementType": 2,
                        "elementId": 8,
                        "elementName": "DEF",
                        "startUnit": null,
                        "endUnit": null,
                        "absences": [
                        {
                            "type": "FROM_TO",
                            "startTime": 1030,
                            "endTime": 1115,
                            "isEvent": false,
                            "startUnit": "4",
                            "endUnit": "4"
                        }
                        ]
                    }
                    """
                    try:
                        absent_list = {1: absent_classes, 2: absent_teachers}[e["elementType"]]
                    except:
                        _LOGGER.error(f"[webuntis-crawler] absentElement has unknown elementType: {e!r}")
                        continue
                    # TODO: find out what e["startUnit"] and e["endUnit"] do
                    name = e["elementName"]
                    absences = []
                    for absence in e["absences"]:
                        if absence["type"] == "ALL_DAY":
                            break
                        elif absence["type"] == "FROM_TO":
                            if absence["startUnit"] == absence["endUnit"]:
                                absences.append(absence["startUnit"])
                            else:
                                absences.append(absence["startUnit"]+"-"+absence["endUnit"])
                        else:
                            _LOGGER.error(f"[webuntis-crawler] absentElement has unknown absence type: {e!r}")
                    else:
                        # loop did not break, no absence was ALL_DAY
                        name += " (" + ", ".join(absences) + ")"
                    absent_list.append(name)
                if absent_classes:
                    day.info.append(("Abwesende Klassen", ", ".join(absent_classes)))
                if absent_teachers:
                    day.info.append(("Abwesende Lehrkräfte", ", ".join(absent_teachers)))

                # MESSAGES
                for message in data["messageData"].pop("messages"):
                    body = _strip_html(message["body"])
                    if subject := message["subject"]:
                        day.info.append((subject, body))
                    else:
                        day.news.append(body)
                if data["messageData"]:
                    _LOGGER.warning(f"[webuntis-crawler] {date_offset} More messageData found: {data['messageData']!r}")

                return last_update
        except Exception as e:
            _LOGGER.error(f"[webuntis-crawler] {date_offset} Failed to parse data: {data}")
            raise e from None
