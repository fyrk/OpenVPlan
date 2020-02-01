import dataclasses
import hashlib
import logging
import re
from functools import lru_cache
from typing import NamedTuple, List, Any, Tuple, Union

from substitution_plan.utils import parse_class_name


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

    def iter_groups(self, selection: Union[List[Tuple[str, str]], str]):
        if selection is None:
            for group in self.substitution_groups:
                yield group
        else:
            for group in self.substitution_groups:
                if group.is_selected(selection):
                    yield group

    def to_dict(self, selection=None):
        groups = self.filter_groups(selection) if selection else self.substitution_groups
        return {key: value for key, value in (("timestamp", self.timestamp), ("name", self.day_name),
                                              ("date", self.date), ("week", self.week), ("news", self.news),
                                              ("info", self.info),
                                              ("groups", [g.to_dict() for g in groups])
                                              ) if value is not None}

    def filter_groups(self, selection):
        for group in self.substitution_groups:
            if group.is_selected(selection):
                yield group


class BaseSubstitutionGroup:
    name: Any
    substitutions: List["BaseSubstitution"]
    group_name_can_be_selected: bool

    def __lt__(self, other):
        raise NotImplementedError

    def to_dict(self):
        return {"name": self.name, "substitutions": [s.to_dict() for s in self.substitutions]}

    def get_raw_name(self):
        return self.name

    def get_html_name(self):
        return self.name

    def is_selected(self, selection):
        raise NotImplementedError


@dataclasses.dataclass
class StudentSubstitutionGroup(BaseSubstitutionGroup):
    name: str
    substitutions: List["BaseSubstitution"]
    split_group_name: Tuple = dataclasses.field(init=False)
    group_name_can_be_selected: bool = dataclasses.field(init=False)

    def __post_init__(self):
        self.split_group_name = parse_class_name(self.name)
        self.group_name_can_be_selected = self.name and \
                                          (self.split_group_name[0] == 0 or len(self.split_group_name[1]) == 1 or
                                           not self.split_group_name[1])

    def __lt__(self, other: "StudentSubstitutionGroup"):
        return self.split_group_name < other.split_group_name

    def is_selected(self, selection: List[Tuple[str, str]]):
        name = self.name.lower()
        return any((selected_class[0] in name and selected_class[1] in name)
                   for selected_class in selection if selected_class[0] or selected_class[1])


@dataclasses.dataclass
class TeacherSubstitutionGroup(BaseSubstitutionGroup):
    name: Tuple[str, bool]  # teacher abbr, is_striked
    substitutions: List["BaseSubstitution"]
    group_name_can_be_selected: bool = dataclasses.field(default=True, init=False)

    def __post_init__(self):
        self.group_name_can_be_selected = self.name[0] != "???"

    def __lt__(self, other):
        return self.name < other.name

    def get_raw_name(self):
        return self.name[0]

    def get_html_name(self):
        if self.name[1]:
            return "<strike>" + self.name[0] + "</strike>"
        return self.name[0]

    def is_selected(self, selection: str):
        print(self.name[0].lower(), "==", selection)
        return self.name[0].lower() == selection


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
