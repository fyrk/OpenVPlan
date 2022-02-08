
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
import logging
from re import T
import time
from typing import Tuple, Optional, Dict, Union, List

import aiohttp

from ..crawlers.base import BaseSubstitutionCrawler
from ..storage import Substitution, SubstitutionDay, SubstitutionGroup, SubstitutionStorage
from ..utils import get_lesson_num


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
    def __init__(self, last_version_id,
                 url: str, format_name: str, max_day_count: int = 5, reorder: List[int] = None,
                 lesson_column: int = None, group_name_is_class: bool = True, affected_groups_columns: List[int] = None,
                 timeout_total: float = None, timeout_connect: float = None, timeout_sock_read: float = None,
                 timeout_sock_connect: float = None):
        super().__init__(last_version_id)
        self._url = url
        self._format_name = format_name
        self._max_day_count = max_day_count
        self._reorder = reorder
        self._lesson_column = lesson_column
        self._group_name_is_class = group_name_is_class
        self._affected_groups_columns = affected_groups_columns
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
            _LOGGER.info(f"Updating substitutions (last_version_id: {self.last_version_id!r})")
            storage = SubstitutionStorage(None, None)
            today = datetime.date.today()
            tasks = [asyncio.ensure_future(self._load_format(session, storage, self._format_name, today, i))
                     for i in range(self._max_day_count)]
            try:
                await asyncio.gather(*tasks)
            except Exception as e:
                for t in tasks:
                    t.cancel()
                raise e

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
                _LOGGER.error(f"[webuntis-crawler] WARNING: Different status for formats: {[t.result() for t in tasks]}")
                reload_required = True

            t = time.perf_counter_ns() - t1
            _LOGGER.debug(f"[webuntis-crawler] Loaded data in {t}ns (~{t/1e9:.2f}s); affected groups: {affected_groups!r}")
            return reload_required, affected_groups
    
    async def _load_format(self,
                           session: aiohttp.ClientSession,
                           storage: SubstitutionStorage,
                           format_name: str,
                           date: datetime.date,
                           date_offset: int) -> str:
        _LOGGER.debug(f"[webuntis-crawler] {date_offset} loading ...")
        t1 = time.perf_counter_ns()
        def log_finish(msg):
            t = time.perf_counter_ns() - t1
            _LOGGER.debug(f"[webuntis-crawler] {date_offset} Finished in {t}ns (~{t/1e9:.2f}s): {msg}")
        async with session.post(self._url, json={
                "formatName": format_name,
                "schoolName": "Gymnasium am Wall",
                "date": int(date.strftime("%Y%m%d")),
                "dateOffset": date_offset,
                "strikethrough": True,
                "mergeBlocks": True,
                "showOnlyFutureSub": False,  # originally True
                "showBreakSupervisions": False,
                "showTeacher": True,
                "showClass": False,  # originally True
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
            }) as r:
            r.raise_for_status()
            try:
                data = await r.json()
            except Exception as e:
                _LOGGER.error(f"[webuntis-crawler] {date_offset} Failed to parse response: {r._body}")
                raise e from None
        try:
            data: dict = data["payload"]
            if data["importInProgress"] is not None:
                _LOGGER.error(f"[webuntis-crawler] WARNING: \"importInProgress\" is {data['importInProgress']!r}")

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

                for row in data["rows"]:
                    subs_data = tuple(_strip_html(s, None) for s in row["data"])
                    if self._lesson_column is not None:
                        lesson_num = get_lesson_num(subs_data[self._lesson_column])
                    else:
                        lesson_num = None
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
                
                for message in data["messageData"].pop("messages"):
                    body = _strip_html(message["body"])
                    if subject := message["subject"]:
                        day.info.append((subject, body))
                    else:
                        day.news.append(body)
                if data["messageData"]:
                    _LOGGER.error(f"[webuntis-crawler] {date_offset} WARNING: More messageData found: {data['messageData']!r}")
                return last_update
        except Exception as e:
            _LOGGER.error(f"[webuntis-crawler] {date_offset} Failed to parse data: {data}")
            raise e from None
