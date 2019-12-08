import re
from functools import lru_cache
from typing import NamedTuple, List, Any


class SubstitutionDay(NamedTuple):
    timestamp: int
    day_name: str
    date: str
    week: str
    news: str
    absent_classes: str
    absent_teachers: str
    substitution_groups: List["BaseSubstitutionGroup"]

    def __lt__(self, other):
        return self.timestamp < other.timestamp

    def to_dict(self, selection=None):
        groups = self.filter_groups(selection) if selection else self.substitution_groups
        return {key: value for key, value in (("timestamp", self.timestamp), ("name", self.day_name),
                                              ("date", self.date), ("week", self.week), ("news", self.news),
                                              ("absent-classes", self.absent_classes),
                                              ("absent-teachers", self.absent_teachers),
                                              ("groups", [g.to_dict() for g in groups])
                                              ) if value is not None}

    def filter_groups(self, selection):
        for group in self.substitution_groups:
            if group.is_selected(selection):
                yield group


class BaseSubstitutionGroup(NamedTuple):
    group_name: Any
    substitutions: List["BaseSubstitution"]

    def __lt__(self, other):
        raise NotImplementedError

    def to_dict(self):
        return {"name": self.group_name, "substitutions": [s.to_dict() for s in self.substitutions]}

    def is_selected(self, parsed_selection):
        raise NotImplementedError


class BaseSubstitution:
    def __init__(self, lesson):
        self.lesson = lesson
        self.lesson_num = get_lesson_num(self.lesson)

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

    def get_text(self):
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
