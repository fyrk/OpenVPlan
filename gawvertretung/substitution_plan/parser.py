import datetime
import re
from abc import ABCMeta, abstractmethod
from html.parser import HTMLParser
from typing import Optional, Callable, Any

from .. import config
from .storage import (StudentSubstitution, TeacherSubstitution, SubstitutionDay,
                                       SubstitutionStorage, BaseSubstitutionGroup, StudentSubstitutionGroup,
                                       BaseSubstitution, TeacherSubstitutionGroup)
from .utils import create_date_timestamp, split_class_name


INCLUDE_OUTDATED_SUBSTITUTIONS = config.get_bool("dev")


_REGEX_STATUS = re.compile(br"Stand: (\d\d\.\d\d\.\d\d\d\d \d\d:\d\d)")


def get_status_string(text, encoding="utf-8", errors="strict"):
    status = _REGEX_STATUS.search(text)
    if status:
        return status.group(1).decode(encoding=encoding, errors=errors)
    raise ValueError(f"Did not find status in {repr(text)}")


class SubstitutionsTooOldException(Exception):
    pass


async def parse_next_site(stream):
    while True:
        line = await stream.readline()
        if not line:
            raise ValueError("Did not find next site")
        if line.startswith(b'<meta http-equiv="refresh" content="8; URL=subst_'):
            return line[49:52]


class BaseSubstitutionParser(HTMLParser, metaclass=ABCMeta):
    REGEX_TITLE = re.compile(r"(\d+.\d+.\d\d\d\d) (\w+), Woche (\w+)")

    def __init__(self, substitution_days_storage: SubstitutionStorage, current_timestamp: int,
                 on_parsed_next_site: Callable[[str], Any] = None):
        # on_parsed_next_site is currently not used. It is an alternative to parse_next_site function.
        super().__init__()
        self._substitution_days_storage = substitution_days_storage
        self._current_timestamp = current_timestamp
        self._on_parsed_next_site = on_parsed_next_site
        self._current_substitution_day: Optional[SubstitutionDay] = None

        self._has_read_news_heading = False
        self._current_section = ""
        self.current_substitution = []
        self._reached_news = False
        self._is_in_tag = False
        self._is_in_td = False
        self._current_news_format_tag = None
        self._current_day_info = None

    def error(self, message):
        pass

    def on_new_substitution_start(self):
        self.current_substitution = []

    def handle_starttag(self, tag, attrs):
        if tag == "td":
            self._is_in_td = True
            if self._current_section == "info-table" and \
                    (self._reached_news or attrs == [("class", "info"), ("colspan", "2")]):
                self._reached_news = True
                self._current_substitution_day.news.append("")
        elif tag == "tr":
            if self._current_section == "substitution-table":
                self.on_new_substitution_start()
        elif tag == "table":
            if len(attrs) == 1 and attrs[0][0] == "class":
                if attrs[0][1] == "info":
                    self._current_section = "info-table"
                elif attrs[0][1] == "mon_list":
                    self._current_section = "substitution-table"
        elif tag == "div":
            if len(attrs) == 1 and attrs[0] == ("class", "mon_title"):
                self._current_section = "title"
        elif tag == "meta":
            if len(attrs) == 2 and attrs[0] == ("http-equiv", "refresh") and attrs[1][0] == "content":
                if self._on_parsed_next_site:
                    self._on_parsed_next_site(attrs[1][1].split("URL=")[1])
        elif self._current_section == "info-table" and self._is_in_td and self._reached_news:
            if tag == "br":
                self._current_substitution_day.news.append("")
            else:
                self._current_substitution_day.news[-1] += "<" + tag + ">"
        self._is_in_tag = True

    @abstractmethod
    def get_current_group_name(self):
        ...

    @abstractmethod
    def create_current_group(self, group_name, substitution: BaseSubstitution) -> BaseSubstitutionGroup:
        ...

    @abstractmethod
    def create_current_substitution(self) -> BaseSubstitution:
        ...

    def handle_endtag(self, tag):
        if self._current_section == "substitution-table":
            if tag == "tr" and self.current_substitution:
                group_name = self.get_current_group_name()
                substitution = self.create_current_substitution()
                try:
                    self._current_substitution_day.get_group(group_name).substitutions.append(substitution)
                except KeyError:
                    self._current_substitution_day.add_group(group_name,
                                                             self.create_current_group(group_name, substitution))
        if tag == "td":
            self._is_in_td = False
        if self._is_in_td and self._current_section == "info-table" and self._reached_news:
            self._current_substitution_day.news[-1] += "</" + tag + ">"
        self._is_in_tag = False

    def handle_data(self, data):
        if self._is_in_tag and self._current_section == "substitution-table":
            self.handle_substitution_data(data)
        elif self._current_section == "info-table":
            if self._is_in_td:
                if not self._reached_news:
                    if self._current_day_info:
                        self._current_substitution_day.info.append((self._current_day_info, data))
                        self._current_day_info = None
                    else:
                        self._current_day_info = data.strip()
                        if self._current_day_info == "Nachrichten zum Tag":
                            self._current_day_info = None
                else:
                    self._current_substitution_day.news[-1] += data
        elif self._current_section == "title":
            match = self.REGEX_TITLE.search(data)
            if match:
                date = match.group(1)
                day_timestamp = create_date_timestamp(datetime.datetime.strptime(date, "%d.%m.%Y"))
                if day_timestamp < self._current_timestamp and not INCLUDE_OUTDATED_SUBSTITUTIONS:
                    raise SubstitutionsTooOldException
                if day_timestamp not in self._substitution_days_storage:
                    self._current_substitution_day = SubstitutionDay(day_timestamp, match.group(2), date,
                                                                     match.group(3))
                    self._substitution_days_storage[day_timestamp] = self._current_substitution_day
                else:
                    self._current_substitution_day = self._substitution_days_storage[day_timestamp]
                self._current_section = None
            else:
                raise ValueError("no date detected in title")

    def handle_substitution_data(self, data):
        if self._is_in_td:
            self.current_substitution.append(data)

    def handle_comment(self, data):
        pass

    def handle_decl(self, data):
        pass

    def close(self):
        super().close()


class StudentSubstitutionParser(BaseSubstitutionParser):
    def __init__(self, substitution_days_storage: SubstitutionStorage, current_timestamp: int):
        super().__init__(substitution_days_storage, current_timestamp)

    def get_current_group_name(self):
        return self.current_substitution[0].strip()

    def create_current_group(self, group_name, substitution: StudentSubstitution) -> BaseSubstitutionGroup:
        return StudentSubstitutionGroup(group_name, [substitution])

    def create_current_substitution(self):
        return StudentSubstitution(*self.current_substitution[1:])


class TeacherSubstitutionParser(BaseSubstitutionParser):
    def __init__(self, substitution_days_storage: SubstitutionStorage, current_timestamp: int):
        super().__init__(substitution_days_storage, current_timestamp)
        self.is_in_strike = False
        self.current_strikes = []

    def get_current_group_name(self):
        # noinspection PyRedundantParentheses
        return (self.current_substitution[0].strip(), self.current_strikes[0])

    def create_current_group(self, group_name, substitution: TeacherSubstitution) -> BaseSubstitutionGroup:
        return TeacherSubstitutionGroup(group_name, [substitution])

    def create_current_substitution(self):
        class_name = self.current_substitution[2]
        if "," in class_name:
            if class_name.startswith("(") and class_name.endswith(")"):
                has_brackets = True
                new_class_name = class_name[1:-1]
            else:
                has_brackets = False
                new_class_name = class_name
            classes = [split_class_name(name.strip()) for name in new_class_name.split(",")]
            if classes[0][0] and all(classes[0][0] == class_[0] for class_ in classes):
                class_name = classes[0][0] + "".join(class_[1] for class_ in classes)
                if has_brackets:
                    class_name = "(" + class_name + ")"
        is_teacher_striked = self.current_strikes[3]
        self.current_strikes = []
        return TeacherSubstitution(
            self.current_substitution[1],
            class_name,
            self.current_substitution[3],
            self.current_substitution[4],
            self.current_substitution[5],
            self.current_substitution[6],
            self.current_substitution[7],
            is_teacher_striked
        )

    def handle_starttag(self, tag, attrs):
        super().handle_starttag(tag, attrs)
        if tag == "strike":
            self.is_in_strike = True

    def handle_endtag(self, tag):
        super().handle_endtag(tag)
        if tag == "strike":
            self.is_in_strike = False

    def handle_substitution_data(self, data):
        if self._is_in_td:
            self.current_strikes.append(self.is_in_strike)
            self.current_substitution.append(data)
