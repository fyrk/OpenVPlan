import dataclasses
import hashlib
import re
from functools import lru_cache
from typing import NamedTuple, List, Any

from substitution_plan.utils import REGEX_CLASS, sort_classes


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


class BaseSubstitutionGroup(NamedTuple):
    name: Any
    substitutions: List["BaseSubstitution"]

    def __lt__(self, other):
        raise NotImplementedError

    def to_dict(self):
        return {"name": self.name, "substitutions": [s.to_dict() for s in self.substitutions]}

    def is_selected(self, parsed_selection):
        raise NotImplementedError


class StudentSubstitutionGroup(BaseSubstitutionGroup):
    def __new__(cls, group_name, substitutions):
        self = super().__new__(cls, group_name, substitutions)
        self._sort_classes = sort_classes(self.name)
        return self

    def __lt__(self, other):
        return self._sort_classes < other._sort_classes

    def is_selected(self, parsed_selection):
        return is_class_selected(self.name, parsed_selection)


class TeacherSubstitutionGroup(BaseSubstitutionGroup):
    def __lt__(self, other):
        return self.name < other.name

    def is_selected(self, parsed_selection):
        return self.name[0] == parsed_selection


class BaseSubstitution:
    def __post_init__(self):
        self.__setattr__("lesson_num", get_lesson_num(self.lesson))

    def __iter__(self):
        raise NotImplementedError

    def to_dict(self):
        raise NotImplementedError

    @lru_cache()
    def get_html_first_of_group(self, group_substitution_count, group, snippets, add_lesson_num):
        raise NotImplementedError

    @lru_cache()
    def get_html(self, snippets, add_lesson_num):
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


def parse_selection(text):
    if not text:
        return []
    selected_classes = []
    for selected_class in "".join(text.split()).split(","):
        if selected_class not in selected_classes:
            selected_classes.append(selected_class)
    return selected_classes


def split_class_name_lower(class_name):
    matches = REGEX_CLASS.search(class_name)
    if matches:
        return matches.group(1).lower(), matches.group(2).lower()
    return "", class_name.lower()


def is_class_selected(class_name, selection):
    if not class_name.strip():
        # class_name is empty, check if empty class name is in selection
        return ("", "") in selection
    class_name = class_name.lower()
    return any((selected_class[0] in class_name and selected_class[1] in class_name)
               for selected_class in selection if selected_class[0] or selected_class[1])


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

    #def __repr__(self):
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
        yield self.lesson_num

    def get_hash(self, date, group_name):
        return hashlib.sha1((date + "-" + group_name[0] + "-" + self.lesson + "." + self.class_name + "." +
                             self.teacher + "." + self.subject + "." + self.room + "." + self.subs_from + "." +
                             self.hint + "." + str(self.is_substitute_striked)).encode()).hexdigest()
