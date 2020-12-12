import datetime
import re
import time
from functools import lru_cache
from typing import List, Tuple, Optional


def create_date_timestamp(date: datetime.datetime):
    return int(time.mktime(date.date().timetuple()))


REGEX_CLASS = re.compile(r"(\d+)([A-Za-z]*)")


def split_class_name(class_name: str) -> Tuple[str, str]:
    matches = REGEX_CLASS.fullmatch(class_name)
    if matches:
        return matches.group(1), matches.group(2)
    return "", class_name


def split_selection(selection: str) -> Optional[List[str]]:
    selected_groups = []
    for selected_group in "".join(selection.split()).split(","):
        if selected_group and selected_group not in selected_groups:
            selected_groups.append(selected_group)
    if not selected_groups:
        return None
    return selected_groups


REGEX_NUMBERS = re.compile(r"\d*")

@lru_cache(maxsize=128)
def get_lesson_num(lesson_string):
    try:
        return max(int(num.group(0)) for num in REGEX_NUMBERS.finditer(lesson_string) if num.group(0) != "")
    except ValueError:  # ValueError for max(...) got empty sequence
        return None
