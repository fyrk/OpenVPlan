import datetime
import re
import time
from typing import List, Tuple, Optional


def create_date_timestamp(date: datetime.datetime):
    return int(time.mktime(date.date().timetuple()))


REGEX_CLASS = re.compile(r"(?:\D|\A)(\d{1,3})([A-Za-z]*)(?:\D|\Z)")


def split_class_name(class_name: str) -> Tuple[str, str]:
    matches = REGEX_CLASS.search(class_name)
    if matches:
        return matches.group(1), matches.group(2)
    return "", class_name


def split_selection(selection: str) -> Optional[List[str]]:
    selection = selection.strip()
    selected_groups = []
    for selected_group in "".join(selection.split()).split(","):
        if selected_group not in selected_groups:
            selected_groups.append(selected_group)
    if not selected_groups:
        return None
    return selected_groups


def split_class_name_lower(class_name):
    matches = REGEX_CLASS.search(class_name)
    if matches:
        return matches.group(1), matches.group(2).lower()
    return "", class_name.lower()
