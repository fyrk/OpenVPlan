import dataclasses
import logging
import re
from functools import lru_cache
from typing import List, Any, Tuple, Optional, Iterable, Dict, Set

from substitution_plan.utils import split_class_name

logger = logging.getLogger()


@dataclasses.dataclass
class SubstitutionDay:
    timestamp: int
    day_name: str
    date: str
    week: str
    news: str
    info: str
    substitution_groups: List["BaseSubstitutionGroup"]

    def __lt__(self, other):
        return self.timestamp < other.timestamp

    def iter_groups(self, selection: Optional[Iterable[str]]):
        if selection is None:
            for group in self.substitution_groups:
                yield group
        else:
            for group in self.substitution_groups:
                if group.is_selected(selection):
                    yield group

    def to_data(self, selection=None):
        return {key: value for key, value in (("timestamp", self.timestamp), ("name", self.day_name),
                                              ("date", self.date), ("week", self.week), ("news", self.news),
                                              ("info", self.info),
                                              ("groups", [g.to_data() for g in self.iter_groups(selection)])
                                              ) if value is not None}

    def get_substitution_sets(self) -> Dict[Any, Set["BaseSubstitution"]]:
        return {group.name: set(group.substitutions) for group in self.substitution_groups}

    def mark_new_substitutions(self, old_groups: Dict[Any, Set["BaseSubstitution"]]):
        for group in self.substitution_groups:
            try:
                group.mark_new_substitutions(old_groups[group.name])
            except KeyError:
                group.mark_all_substitutions_as_new()


class BaseSubstitutionGroup:
    name: Any
    substitutions: List["BaseSubstitution"]
    affected_groups: Optional[List[str]]
    affected_groups_pretty: Optional[List[str]]

    def __lt__(self, other):
        raise NotImplementedError

    def to_data(self):
        return {"name": self.name, "substitutions": [s.to_data() for s in self.substitutions]}

    def get_html_name(self):
        return self.name

    def is_selected(self, selection: Iterable[str]):
        if not self.affected_groups:
            return False
        return any(g in selection for g in self.affected_groups)

    def mark_new_substitutions(self, old_substitutions: Set["BaseSubstitution"]):
        for s in self.substitutions:
            if s not in old_substitutions:
                s.is_new = True

    def mark_all_substitutions_as_new(self):
        for s in self.substitutions:
            s.is_new = True


@dataclasses.dataclass
class StudentSubstitutionGroup(BaseSubstitutionGroup):
    name: str
    substitutions: List["BaseSubstitution"]
    split_group_name: Tuple = dataclasses.field(init=False)
    affected_groups: Optional[List[str]] = dataclasses.field(init=False)
    affected_groups_pretty: Optional[List[str]] = dataclasses.field(init=False)

    def __post_init__(self):
        number, letters = split_class_name(self.name)
        self.split_group_name = (int(number) if number else 0, letters)
        letters_upper = letters.upper()
        if number:
            if letters:
                self.affected_groups = [number + letter for letter in letters_upper]
                self.affected_groups_pretty = [number + letter for letter in letters]
            else:
                self.affected_groups = self.affected_groups_pretty = [number]
        elif self.name:
            self.affected_groups = [letters_upper]
            self.affected_groups_pretty = [letters]
        else:
            self.affected_groups = self.affected_groups_pretty = None

    def __lt__(self, other: "StudentSubstitutionGroup"):
        return self.split_group_name < other.split_group_name


@dataclasses.dataclass
class TeacherSubstitutionGroup(BaseSubstitutionGroup):
    name: Tuple[str, bool]  # teacher abbr, is_striked
    substitutions: List["BaseSubstitution"]
    affected_groups: Optional[List[str]] = dataclasses.field(init=False)
    affected_groups_pretty: Optional[List[str]] = dataclasses.field(init=False)

    def __post_init__(self):
        if self.name[0] != "???":
            self.affected_groups = [self.name[0].upper()]
            self.affected_groups_pretty = [self.name[0]]
        else:
            self.affected_groups = self.affected_groups_pretty = None

    def __lt__(self, other):
        return self.name < other.name

    def get_html_name(self):
        if self.name[1]:
            return "<strike>" + self.name[0] + "</strike>"
        return self.name[0]


class BaseSubstitution:
    lesson: str
    is_new: bool

    def __post_init__(self):
        self.lesson_num = get_lesson_num(self.lesson)

    def __iter__(self):
        raise NotImplementedError

    def to_data(self):
        return dataclasses.astuple(self)


REGEX_NUMBERS = re.compile(r"\d*")


@lru_cache(maxsize=128)
def get_lesson_num(lesson_string):
    # noinspection PyBroadException
    try:
        return max(int(num.group(0)) for num in REGEX_NUMBERS.finditer(lesson_string)
                   if num.group(0) != "")
    except Exception:
        return None


@dataclasses.dataclass(unsafe_hash=True)
class StudentSubstitution(BaseSubstitution):
    teacher: str
    substitute: str
    lesson: str
    subject: str
    room: str
    subs_from: str
    hint: str
    lesson_num: int = dataclasses.field(init=False, hash=False)
    is_new: bool = dataclasses.field(default=False, init=False, hash=False)

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
    lesson_num: int = dataclasses.field(init=False, hash=False)
    is_new: bool = dataclasses.field(default=False, init=False, hash=False)

    def __iter__(self):
        yield self.lesson
        yield self.class_name
        yield self.teacher
        yield self.subject
        yield self.room
        yield self.subs_from
        yield self.hint
