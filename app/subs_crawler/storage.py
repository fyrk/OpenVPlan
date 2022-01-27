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

import dataclasses
import datetime
from typing import Dict, Iterable, List, Optional, Tuple, Union

from sortedcontainers import SortedDict, SortedKeysView, SortedList

from .utils import split_class_name, parse_affected_groups


class SubstitutionStorage:
    def __init__(self, status: str, status_datetime: datetime.datetime):
        self.status = status
        self.status_datetime = status_datetime
        self._days: SortedDict = SortedDict()

    def add_day(self, day: "SubstitutionDay"):
        assert day.date not in self._days
        self._days[day.date] = day

    def get_day(self, date: datetime.date):
        return self._days[date]

    def has_day(self, date: datetime.date):
        return date in self._days

    def iter_days(self):
        yield from self._days.values()

    def get_new_affected_groups(self, old_storage: Optional["SubstitutionStorage"]) \
            -> Dict[int, Dict[str, Union[str, List[str]]]]:
        """
        :return: {<day expiry time>:
        {"name": "<day name">, "groups": list of group names which are affected by new substitutions from this day}}
        """
        if old_storage is None:
            return {day.date: {"name": day.name, "groups": day.get_new_affected_groups(None)}
                    for day in self._days.values()}
        affected_groups = {}
        for day in self._days.values():
            try:
                old_day = old_storage.get_day(day.date)
            except KeyError:
                affected_groups[day.date] = {"name": day.name, "groups": day.get_new_affected_groups(None)}
            else:
                if g := day.get_new_affected_groups(old_day):
                    affected_groups[day.date] = {"name": day.name, "groups": g}
        return affected_groups

    def remove_old_days(self) -> bool:
        current_date = datetime.date.today()
        # noinspection PyTypeChecker
        dates: SortedKeysView = self._days.keys()
        changed = False
        while dates and dates[0] < current_date:
            del dates[0]
            changed = True
        return changed

    def to_data(self, selection=None):
        return {"status": self.status, "days": [d.to_data(selection) for d in self._days.values()]}


@dataclasses.dataclass
class SubstitutionDay:
    date: datetime.date
    name: str
    datestr: str
    week: str
    news: List[str] = dataclasses.field(init=False, default_factory=list)
    info: List[Tuple[str, str]] = dataclasses.field(init=False, default_factory=list)
    _groups: SortedList = dataclasses.field(init=False, default_factory=SortedList)
    _id2group: Dict[Tuple[str, bool], "SubstitutionGroup"] = dataclasses.field(init=False, default_factory=dict)

    def add_group(self, group: "SubstitutionGroup"):
        assert group.id not in self._id2group, f"{group.id} already exists"
        self._groups.add(group)
        self._id2group[group.id] = group

    def get_group(self, group_id: Tuple[str, bool], default=None):
        return self._id2group.get(group_id, default)

    def __lt__(self, other: "SubstitutionDay"):
        return self.date < other.date

    @property
    def groups(self):
        return self._groups

    def get_new_affected_groups(self, old_day: Optional["SubstitutionDay"]) -> List[str]:
        res = []
        if old_day is None:
            for g in self._groups:
                for affected_group in g.affected_groups:
                    if affected_group not in res:
                        res.append(affected_group)
            return res
        for g in self._groups:
            if g.has_new_substitutions(old_day.get_group(g.id)):
                for affected_group in g.affected_groups:
                    if affected_group not in res:
                        res.append(affected_group)
        return res

    def to_data(self, selection=None):
        return {key: value for key, value in (("date", self.date),
                                              ("name", self.name),
                                              ("datestr", self.datestr),
                                              ("week", self.week),
                                              ("news", self.news),
                                              ("info", self.info),
                                              ("groups", [g.to_data() for g in self.iter_groups(selection)])
                                              ) if value is not None}


@dataclasses.dataclass(frozen=True)
class SubstitutionGroup:
    name: str
    _split_name: Tuple[int, str, bool] = dataclasses.field(init=False, compare=False)
    striked: bool
    substitutions: List["Substitution"] = dataclasses.field(default_factory=list)
    id: Tuple[str, bool] = dataclasses.field(init=False, compare=False)
    affected_groups: Optional[List[str]] = dataclasses.field(init=False, compare=False)
    selection_name: Optional[str] = dataclasses.field(init=False, compare=False)

    name_is_class: dataclasses.InitVar[bool] = True

    def __post_init__(self, name_is_class):
        object.__setattr__(self, "id", (self.name, self.striked))
        number_part, letters_part = split_class_name(self.name)
        object.__setattr__(self, "_split_name", (int(number_part) if number_part else 0, letters_part, self.striked))
        if name_is_class:
            affected_groups, selection_name = parse_affected_groups(self.name)
            object.__setattr__(self, "affected_groups", affected_groups)
            object.__setattr__(self, "selection_name", selection_name)
        else:
            object.__setattr__(self, "affected_groups", {self.name})
            object.__setattr__(self, "selection_name", self.name)

    def __lt__(self, other: "SubstitutionGroup"):
        if not self.name:
            return False  # sort substitutions without a class last
        return self._split_name.__lt__(other._split_name)
    
    def get_selected_substitutions(self, selection=None):
        if (
            not selection or
            not self.name  # always include substitutions without a class
            or any(s in self.affected_groups for s in selection)
        ):
            return self.substitutions
        return [subs for subs in self.substitutions if subs.is_selected(selection)]

    def get_html_name(self):
        return ("<strike>" + self.name + "</strike>") if self.striked else self.name

    def has_new_substitutions(self, old_group: Optional["SubstitutionGroup"]):
        if old_group is None:
            return True
        return any(s not in old_group.substitutions for s in self.substitutions)

    def to_data(self):
        data = {"name": self.name}
        if self.striked:
            data["striked"] = self.striked
        data["substitutions"] = [s.to_data() for s in self.substitutions]
        return data


@dataclasses.dataclass(frozen=True)
class Substitution:
    data: Tuple[str, ...]
    lesson_num: Optional[int] = dataclasses.field(default=None)

    affected_groups: Optional[List[str]] = dataclasses.field(init=False, compare=False)

    name_is_class: dataclasses.InitVar[bool] = True
    affected_groups_columns: dataclasses.InitVar[List[int]] = []

    def __post_init__(self, name_is_class, affected_groups_columns):
        if affected_groups_columns:
            affected_groups = set()
            for column in affected_groups_columns:
                content = self.data[column-1]
                if name_is_class:
                    affected_groups.update(parse_affected_groups(content)[0])
                else:
                    affected_groups.add(content)
        else:
            affected_groups = None
        object.__setattr__(self, "affected_groups", affected_groups)

    def is_selected(self, selection=None):
        if self.affected_groups is None:
            return False
        return any(s in self.affected_groups for s in selection)

    def to_data(self):
        return self.data
