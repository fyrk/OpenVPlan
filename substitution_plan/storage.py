import dataclasses
import hashlib
import logging
import re
from functools import lru_cache
from typing import NamedTuple, List, Any, Tuple, Optional, Iterable

from substitution_plan.utils import split_class_name

logger = logging.getLogger()


class SubstitutionDay(NamedTuple):
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

    def to_dict(self, selection=None):
        return {key: value for key, value in (("timestamp", self.timestamp), ("name", self.day_name),
                                              ("date", self.date), ("week", self.week), ("news", self.news),
                                              ("info", self.info),
                                              ("groups", [g.to_dict() for g in self.iter_groups(selection)])
                                              ) if value is not None}


class BaseSubstitutionGroup:
    name: Any
    substitutions: List["BaseSubstitution"]
    affected_groups: Optional[List[str]]

    def __lt__(self, other):
        raise NotImplementedError

    def to_dict(self):
        return {"name": self.name, "substitutions": [s.to_dict() for s in self.substitutions]}

    def get_html_name(self):
        return self.name

    def is_selected(self, selection: Iterable[str]):
        if not self.affected_groups:
            return False
        return any(g in selection for g in self.affected_groups)


@dataclasses.dataclass
class StudentSubstitutionGroup(BaseSubstitutionGroup):
    name: str
    substitutions: List["BaseSubstitution"]
    split_group_name: Tuple = dataclasses.field(init=False)
    affected_groups: Optional[List[str]] = dataclasses.field(init=False)

    def __post_init__(self):
        number, letters = split_class_name(self.name)
        self.split_group_name = (int(number) if number else 0, letters)
        if number:
            if letters:
                self.affected_groups = [number + letter for letter in letters]
            else:
                self.affected_groups = [number]
        elif self.name:
            self.affected_groups = [letters]
        else:
            self.affected_groups = None

    def __lt__(self, other: "StudentSubstitutionGroup"):
        return self.split_group_name < other.split_group_name


@dataclasses.dataclass
class TeacherSubstitutionGroup(BaseSubstitutionGroup):
    name: Tuple[str, bool]  # teacher abbr, is_striked
    substitutions: List["BaseSubstitution"]
    affected_groups: Optional[List[str]] = dataclasses.field(init=False)

    def __post_init__(self):
        if self.name[0] != "???":
            self.affected_groups = [self.name[0]]
        else:
            self.affected_groups = None

    def __lt__(self, other):
        return self.name < other.name

    def get_html_name(self):
        if self.name[1]:
            return "<strike>" + self.name[0] + "</strike>"
        return self.name[0]


class BaseSubstitution:
    def __post_init__(self):
        self.__setattr__("lesson_num", get_lesson_num(self.lesson))

    def __iter__(self):
        raise NotImplementedError

    def to_dict(self):
        raise NotImplementedError

    def get_hash(self, date, group_name):
        raise NotImplementedError


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
    lesson_num: int = dataclasses.field(init=False)

    def to_dict(self):
        return dataclasses.asdict(self, dict_factory=lambda x: {k: v for k, v in x if v is not None})

    def __iter__(self):
        yield self.teacher
        yield self.substitute
        yield self.lesson
        yield self.subject
        yield self.room
        yield self.subs_from
        yield self.hint

    @lru_cache()
    def get_hash(self, date, class_name):
        return hashlib.sha1((date + "-" + class_name + "-" + self.teacher + "." + self.substitute + "." + self.lesson +
                             "." + self.subject + "." + self.room + "." + self.subs_from + "." + self.hint)
                            .encode()).hexdigest()


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
    lesson_num: int = dataclasses.field(init=False)

    # def __repr__(self):
    #    return f"TeacherSubstitution({self.lesson}, {self.class_name}, {self.teacher}, {self.subject}, {self.room}, " \
    #           f"{self.subs_from}, {self.hint}, {self.is_substitute_striked})"

    def to_dict(self):
        return dataclasses.asdict(self, dict_factory=lambda x: {k: v for k, v in x if v is not None})

    def __iter__(self):
        yield self.lesson
        yield self.class_name
        yield self.teacher
        yield self.subject
        yield self.room
        yield self.subs_from
        yield self.hint

    def get_hash(self, date, group_name):
        return hashlib.sha1((date + "-" + group_name[0] + "-" + self.lesson + "." + self.class_name + "." +
                             self.teacher + "." + self.subject + "." + self.room + "." + self.subs_from + "." +
                             self.hint + "." + str(self.is_substitute_striked)).encode()).hexdigest()
