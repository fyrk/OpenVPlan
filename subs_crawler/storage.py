import dataclasses
import datetime
from typing import Dict, Iterable, List, Optional, Tuple, Union

from sortedcontainers import SortedDict, SortedKeysView, SortedList

from subs_crawler.utils import split_class_name


class SubstitutionStorage:
    def __init__(self, status: str, status_datetime: datetime.datetime):
        self._last_updated = datetime.datetime.now()
        self._status = status
        self._status_datetime = status_datetime
        self._days: SortedDict = SortedDict()

    def add_day(self, day: "SubstitutionDay"):
        assert day.expiry_time not in self._days
        self._days[day.expiry_time] = day

    def get_day(self, expiry_time: int):
        return self._days[expiry_time]

    def has_day(self, expiry_time: int):
        return expiry_time in self._days

    def iter_days(self):
        yield from self._days.values()

    @property
    def status(self):
        return self._status

    @property
    def status_datetime(self):
        return self._status_datetime

    @property
    def last_updated(self):
        return self._last_updated

    def get_new_affected_groups(self, old_storage: Optional["SubstitutionStorage"]) \
            -> Dict[int, Dict[str, Union[str, List[str]]]]:
        """
        :return: {<day expiry time>:
        {"name": "<day name">, "groups": list of group names which are affected by new substitutions from this day}}
        """
        if old_storage is None:
            return {day.expiry_time: {"name": day.name, "groups": day.get_new_affected_groups(None)}
                    for day in self._days.values()}
        affected_groups = {}
        for day in self._days.values():
            try:
                old_day = old_storage.get_day(day.expiry_time)
            except KeyError:
                affected_groups[day.expiry_time] = {"name": day.name, "groups": day.get_new_affected_groups(None)}
            else:
                if g := day.get_new_affected_groups(old_day):
                    affected_groups[day.expiry_time] = {"name": day.name, "groups": g}
        return affected_groups

    def remove_old_days(self) -> bool:
        self._last_updated = datetime.datetime.now()
        current_timestamp = self._last_updated.timestamp()
        # noinspection PyTypeChecker
        expiry_times: SortedKeysView = self._days.keys()
        changed = False
        while expiry_times and expiry_times[0] <= current_timestamp:
            del expiry_times[0]
            changed = True
        return changed

    def to_data(self, selection=None):
        return {"last_updated": self._last_updated, "status": self.status,
                "days": [d.to_data(selection) for d in self._days.values()]}


@dataclasses.dataclass
class SubstitutionDay:
    timestamp: int
    expiry_time: int
    name: Optional[str]
    date: Optional[str]
    week: Optional[str]
    news: List[str] = dataclasses.field(init=False, default_factory=list)
    info: List[Tuple[str, str]] = dataclasses.field(init=False, default_factory=list)
    _groups: SortedList = dataclasses.field(init=False, default_factory=SortedList)
    _id2group: Dict[Tuple[str, bool], "SubstitutionGroup"] = dataclasses.field(init=False, default_factory=dict)

    def add_group(self, group: "SubstitutionGroup"):
        group_id = (group.name, group.striked)
        assert group_id not in self._id2group
        self._groups.add(group)
        self._id2group[group_id] = group

    def get_group(self, group_id: Tuple[str, bool], default=None):
        return self._id2group.get(group_id, default)

    def __lt__(self, other: "SubstitutionDay"):
        return self.expiry_time < other.expiry_time

    def iter_groups(self, selection: Optional[Iterable[str]]):
        if not selection:
            for group in self._groups:
                yield group
        else:
            for group in self._groups:
                if group.is_selected(selection):
                    yield group

    def get_new_affected_groups(self, old_day: Optional["SubstitutionDay"]) -> List[str]:
        res = []
        if old_day is None:
            for g in self._groups:
                for affected_group in g.affected_groups:
                    if affected_group not in res:
                        res.append(affected_group)
            return res
        for g in self._groups:
            if g.has_new_substitutions(old_day.get_group(g.name)):
                for affected_group in g.affected_groups:
                    if affected_group not in res:
                        res.append(affected_group)
        return res

    def to_data(self, selection=None):
        return {key: value for key, value in (("timestamp", self.timestamp),
                                              ("expiry_time", self.expiry_time),
                                              ("name", self.name),
                                              ("date", self.date),
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
    affected_groups: Optional[List[str]] = dataclasses.field(init=False, compare=False, default_factory=list)

    def __post_init__(self):
        number_part, letters_part = split_class_name(self.name)
        object.__setattr__(self, "_split_name", (int(number_part) if number_part else 0, letters_part, self.striked))
        letters_upper = letters_part.upper()
        if number_part:
            if letters_part:
                self.affected_groups.extend(number_part + letter for letter in letters_upper)
            else:
                self.affected_groups.append(number_part)
        else:
            if self.name:
                self.affected_groups.append(letters_upper)

    def __lt__(self, other: "SubstitutionGroup"):
        return self._split_name.__lt__(other._split_name)

    def is_selected(self, selection=None):
        if not self.affected_groups:
            return False
        return any(any(s in g for s in selection) for g in self.affected_groups)

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

    def to_data(self):
        return self.data
