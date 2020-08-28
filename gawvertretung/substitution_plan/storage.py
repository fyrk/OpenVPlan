import dataclasses
import re
from abc import ABC, abstractmethod
from functools import lru_cache
from typing import List, Tuple, Optional, Iterable, Dict

from sortedcontainers import SortedDict, SortedList, SortedSet

from ..substitution_plan.utils import split_class_name


class SubstitutionStorage(SortedDict):
    def __init__(self, status: str):
        super().__init__()
        self._status = status

    @classmethod
    def _unpickle(cls, key, items, status):
        s = cls.__new__(cls)
        SortedDict.__init__(s, key, items)
        s._status = status
        return s

    def __reduce__(self):
        # this method is overridden so that unpickling works
        # it doesn't work with SortedDict's __reduce__ because it calls __init__ - but __init__ has been overridden
        items = dict.copy(self)
        return self._unpickle, (self._key, items, self._status)

    @property
    def status(self):
        return self._status

    def to_data(self, selection=None):
        return [day.to_data(selection) for day in self.values()]

    def mark_new_substitutions(self, old_storage: "SubstitutionStorage") -> Dict[str, List[str]]:
        """
        :return: a dict: {day_name: list of group names which are affected by new substitutions from this day}
        """
        affected_groups = {}
        for day in self.values():
            try:
                old_day = old_storage[day.timestamp]
            except KeyError:
                affected_groups[day.day_name] = day.get_all_affected_groups()
            else:
                new_subs = day.mark_new_substitutions(old_day)
                if new_subs:
                    affected_groups[day.day_name] = new_subs
        return affected_groups

    def get_all_affected_groups(self) -> Dict[str, List[str]]:
        affected_groups = {}
        for day in self.values():
            groups = []
            for group in day.iter_groups(None):
                if group.affected_groups:
                    groups.extend(group.affected_groups)
            affected_groups[day.day_name] = groups
        return affected_groups

    # noinspection PyUnresolvedReferences
    def remove_old_days(self, current_timestamp: int):
        timestamps = self.keys()
        while timestamps and timestamps[0] < current_timestamp:
            del timestamps[0]


@dataclasses.dataclass
class SubstitutionDay:
    timestamp: int
    day_name: Optional[str]
    date: Optional[str]
    week: Optional[str]
    news: List[str] = dataclasses.field(init=False, default_factory=list)
    info: List[Tuple[str, str]] = dataclasses.field(init=False, default_factory=list)
    _group_name2group: Dict[str, "BaseSubstitutionGroup"] = dataclasses.field(init=False, default_factory=dict)
    _substitution_groups: SortedList = dataclasses.field(init=False, default_factory=SortedList)

    def get_group(self, group_name: str):
        return self._group_name2group[group_name]

    def add_group(self, group_name: str, group: "BaseSubstitutionGroup"):
        self._group_name2group[group_name] = group
        self._substitution_groups.add(group)

    def __lt__(self, other: "SubstitutionDay"):
        return self.timestamp < other.timestamp

    def iter_groups(self, selection: Optional[Iterable[str]]):
        if not selection:
            for group in self._substitution_groups:
                yield group
        else:
            for group in self._substitution_groups:
                if group.is_selected(selection):
                    yield group

    def to_data(self, selection=None):
        return {key: value for key, value in (("timestamp", self.timestamp), ("name", self.day_name),
                                              ("date", self.date), ("week", self.week), ("news", self.news),
                                              ("info", self.info),
                                              ("groups", [g.to_data() for g in self.iter_groups(selection)])
                                              ) if value is not None}

    def mark_new_substitutions(self, old_day: "SubstitutionDay") -> List[str]:
        affected_groups: List[str] = []
        for name, group in self._group_name2group.items():
            try:
                old_group = old_day.get_group(name)
            except KeyError:
                group.mark_all_substitutions_as_new()
                if group.affected_groups is not None:
                    for g in group.affected_groups:
                        if g not in affected_groups:  # TODO improve
                            affected_groups.extend(group.affected_groups)
            else:
                if group.mark_new_substitutions(old_group.substitutions):
                    # at least one substitution in group 'group' is new
                    if group.affected_groups:
                        for g in group.affected_groups:
                            if g not in affected_groups:  # TODO improve
                                affected_groups.append(g)
        return affected_groups

    def get_all_affected_groups(self) -> List[str]:
        affected_groups: List[str] = []
        for group in self._substitution_groups:
            if group.affected_groups:
                for g in group.affected_groups:
                    if g not in affected_groups:
                        affected_groups.append(g)
        return affected_groups


@dataclasses.dataclass
class BaseSubstitutionGroupName(ABC):
    name: str

    def get_affected_groups(self) -> Tuple[Optional[List[str]], Optional[List[str]]]:
        raise NotImplementedError

    def to_html(self):
        return self.name


@dataclasses.dataclass
class StudentSubstitutionGroupName(BaseSubstitutionGroupName):
    split_name: Tuple[int, str] = dataclasses.field(init=False, hash=False, compare=False)
    _number_part: str = dataclasses.field(init=False, hash=False, compare=False)
    _letters_part: str = dataclasses.field(init=False, hash=False, compare=False)

    def __post_init__(self):
        self._number_part, self._letters_part = split_class_name(self.name)
        self.split_name = (int(self._number_part) if self._number_part else 0, self._letters_part)

    def get_affected_groups(self) -> Tuple[Optional[List[str]], Optional[List[str]]]:
        letters_upper = self._letters_part.upper()
        if self._number_part:
            if self._letters_part:
                return ([self._number_part + letter for letter in letters_upper],
                        [self._number_part + letter for letter in self._letters_part])
            else:
                return [self._number_part], [self._number_part]
        if self.name:
            return [letters_upper], [self._letters_part]
        return None, None

    def __lt__(self, other: "StudentSubstitutionGroupName"):
        return self.split_name.__lt__(other.split_name)


@dataclasses.dataclass
class TeacherSubstitutionGroupName(BaseSubstitutionGroupName):
    is_striked: bool

    def get_affected_groups(self) -> Tuple[Optional[List[str]], Optional[List[str]]]:
        if self.name != "???":
            return [self.name.upper()], [self.name]
        return None, None

    def to_html(self):
        if self.is_striked:
            return "<strike>" + self.name + "</strike>"
        return self.name

    def __lt__(self, other: "TeacherSubstitutionGroupName"):
        if self.name == other.name:
            return self.is_striked.__lt__(other.is_striked)
        return self.name.__lt__(other.name)


@dataclasses.dataclass
class BaseSubstitutionGroup(ABC):
    name: BaseSubstitutionGroupName
    substitutions: List["BaseSubstitution"] = dataclasses.field(default_factory=list)
    affected_groups: Optional[List[str]] = dataclasses.field(init=False)
    affected_groups_pretty: Optional[List[str]] = dataclasses.field(init=False)

    def __post_init__(self):
        self.affected_groups, self.affected_groups_pretty = self.name.get_affected_groups()

    def __lt__(self, other):
        return self.name.__lt__(other.name)

    def to_data(self):
        return {"name": self.name, "substitutions": [s.to_data() for s in self.substitutions]}

    def is_selected(self, selection: Iterable[str]):
        if not self.affected_groups:
            return False
        return any(g in selection for g in self.affected_groups)

    def mark_new_substitutions(self, old_substitutions: List["BaseSubstitution"]) -> bool:
        has_new_substitutions = False
        for s in self.substitutions:
            if s not in old_substitutions:
                has_new_substitutions = True
                s.is_new = True
        return has_new_substitutions

    def mark_all_substitutions_as_new(self):
        for s in self.substitutions:
            s.is_new = True


@dataclasses.dataclass
class StudentSubstitutionGroup(BaseSubstitutionGroup):
    def __init__(self, name: str, substitutions: List["BaseSubstitution"]):
        super().__init__(StudentSubstitutionGroupName(name), substitutions)


@dataclasses.dataclass
class TeacherSubstitutionGroup(BaseSubstitutionGroup):
    def __init__(self, name: Tuple[str, bool], substitutions: List["BaseSubstitution"]):
        super().__init__(TeacherSubstitutionGroupName(*name), substitutions)


REGEX_NUMBERS = re.compile(r"\d*")


@lru_cache(maxsize=128)
def get_lesson_num(lesson_string):
    try:
        return max(int(num.group(0)) for num in REGEX_NUMBERS.finditer(lesson_string) if num.group(0) != "")
    except ValueError:  # ValueError for max(...) got empty sequence
        return None


@dataclasses.dataclass
class BaseSubstitution(ABC):
    lesson_num: int = dataclasses.field(init=False, compare=False)
    is_new: bool = dataclasses.field(default=False, init=False, compare=False)

    def __post_init__(self):
        # self.lesson is added by subclasses
        # noinspection PyUnresolvedReferences
        self.lesson_num = get_lesson_num(self.lesson)

    @abstractmethod
    def __iter__(self):
        ...

    def to_data(self):
        return dataclasses.astuple(self)


@dataclasses.dataclass(unsafe_hash=True)
class StudentSubstitution(BaseSubstitution):
    teacher: str
    substitute: str
    lesson: str
    subject: str
    room: str
    subs_from: str
    hint: str

    def __iter__(self):
        yield self.teacher
        yield self.substitute
        yield self.lesson
        yield self.subject
        yield self.room
        yield self.subs_from
        yield self.hint


@dataclasses.dataclass(unsafe_hash=True)
class TeacherSubstitution(BaseSubstitution):
    lesson: str
    class_name: str
    teacher: str
    subject: str
    room: str
    subs_from: str
    hint: str
    is_substitute_striked: bool

    def __iter__(self):
        yield self.lesson
        yield self.class_name
        yield self.teacher
        yield self.subject
        yield self.room
        yield self.subs_from
        yield self.hint
