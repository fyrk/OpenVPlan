import datetime
import hashlib
import re
import time

REGEX_STATUS = re.compile(br"Stand: (\d\d\.\d\d\.\d\d\d\d \d\d:\d\d)")

REGEX_CLASS = re.compile(r"(?:\D|\A)(\d{1,3})([A-Za-z]*)(?:\D|\Z)")


def create_date_timestamp(date: datetime.datetime):
    return int(time.mktime(date.date().timetuple()))


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


def sort_classes(class_name):
    matches = REGEX_CLASS.search(class_name)
    if matches:
        return int(matches.group(1)), matches.group(2)
    return 0, class_name


def obfuscate_chat_id(chat_id) -> str:
    return hashlib.sha224(int(chat_id).to_bytes(5, "big") +
                          int(time.mktime(datetime.datetime.now().date().timetuple()))
                          .to_bytes(5, "big")).hexdigest()[:7]

