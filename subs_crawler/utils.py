import datetime
import re
import time
from functools import lru_cache
from typing import List, Tuple, Optional, Set


def create_date_timestamp(date: datetime.datetime):
    return int(time.mktime(date.date().timetuple()))


REGEX_GROUP_NAME = re.compile(r"^(\d+)(.*)")

def split_class_name(class_name: str) -> Tuple[str, str]:
    matches = REGEX_GROUP_NAME.fullmatch(class_name)
    if matches:
        return matches.group(1), matches.group(2)
    return "", class_name


REGEX_CLASS = re.compile(r"^(\d+)([A-Za-z]*)")

def parse_affected_groups(class_name: str) -> Tuple[Set[str], Optional[str]]:
    name = class_name.upper().strip()
    if not name:
        return set(), None
    affected_groups = set()
    count = 0
    while name:
        match = REGEX_CLASS.match(name)
        if match is None:
            return {class_name}, None
        count += 1
        digits, letters = match.groups()
        affected_groups.add(digits)
        if len(letters) > 1:
            count += 1
        for letter in letters:
            affected_groups.add(digits + letter)
        name = name[match.span()[1]:]
    return affected_groups, class_name if count == 1 else None


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
