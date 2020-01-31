import datetime
import re
import time


def create_date_timestamp(date: datetime.datetime):
    return int(time.mktime(date.date().timetuple()))


REGEX_CLASS = re.compile(r"(?:\D|\A)(\d{1,3})([A-Za-z]*)(?:\D|\Z)")


def parse_class_name(class_name):
    matches = REGEX_CLASS.search(class_name)
    if matches:
        return int(matches.group(1)), matches.group(2)
    return 0, class_name


def split_class_name(class_name):
    matches = REGEX_CLASS.search(class_name)
    if matches:
        return matches.group(1), matches.group(2)
    return "", class_name


def parse_class_selection(selection: str):
    selection = selection.strip()
    if not selection:
        return None
    selected_classes = []
    for selected_class in "".join(selection.split()).split(","):
        if selected_class not in selected_classes:
            selected_classes.append(selected_class)
    return selected_classes, [split_class_name_lower(class_name) for class_name in selected_classes]


def split_class_name_lower(class_name):
    matches = REGEX_CLASS.search(class_name)
    if matches:
        return matches.group(1), matches.group(2).lower()
    return "", class_name.lower()
