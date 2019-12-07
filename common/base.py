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


class BaseSubstitutionGroup(NamedTuple):
    group_name: Any
    substitutions: List["BaseSubstitution"]

    def __lt__(self, other):
        raise NotImplementedError


class BaseSubstitution:
    def __init__(self, lesson):
        self.lesson = lesson
        self.lesson_num = get_lesson_num(self.lesson)

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
        return "lesson" + str(max(int(num.group(0)) for num in REGEX_NUMBERS.finditer(lesson_string)
                                  if num.group(0) != ""))
    except Exception:
        return ""
