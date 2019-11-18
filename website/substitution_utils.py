import datetime
import re
from functools import lru_cache

REGEX_STATUS = re.compile(br"Stand: (\d\d\.\d\d\.\d\d\d\d \d\d:\d\d)")

REGEX_CLASS = re.compile(r"(?:\D|\A)(\d{1,3})([A-Za-z]*)(?:\D|\Z)")

REGEX_NUMBERS = re.compile(r"\d*")


@lru_cache(maxsize=128)
def get_lesson_num(lesson_string):
    try:
        return "lesson" + str(max(int(num.group(0)) for num in REGEX_NUMBERS.finditer(lesson_string)
                                  if num.group(0) != ""))
    except Exception:
        return ""


def create_date_timestamp(date):
    return int(datetime.datetime.strptime(date, "%d.%m.%Y").timestamp())


def get_status_string(text):
    status = REGEX_STATUS.search(text)
    if status:
        return status.group(1).decode("iso-8859-1")
    raise ValueError


def split_class_name(class_name):
    matches = REGEX_CLASS.search(class_name)
    if matches:
        return matches.group(1), matches.group(2)
    return "", class_name


def split_class_name_lower(class_name):
    matches = REGEX_CLASS.search(class_name)
    if matches:
        return matches.group(1).lower(), matches.group(2).lower()
    return "", class_name.lower()


def sort_classes(class_name):
    matches = REGEX_CLASS.search(class_name)
    if matches:
        return int(matches.group(1)), matches.group(2)
    if "<" in class_name:
        matches = re.search(r">(.*?)<", class_name)
        if matches:
            return 0, matches.group(1)
    return 0, class_name


def do_class_names_match(class_name, selected_class):
    class_name = class_name.lower()
    return selected_class[0].lower() in class_name and selected_class[1].lower() in class_name
