import datetime
import re
from html.parser import HTMLParser

from substitution_plan.storage import StudentSubstitution, TeacherSubstitution
from substitution_plan.utils import create_date_timestamp, split_class_name


async def parse_next_site(stream):
    while True:
        line = await stream.readline()
        if not line:
            raise ValueError("Did not find next site")
        if line.startswith(b'<meta http-equiv="refresh" content="8; URL=subst_'):
            return line[49:52]


REGEX_STATUS = re.compile(br"Stand: (\d\d\.\d\d\.\d\d\d\d \d\d:\d\d)")


def get_status_string(text):
    status = REGEX_STATUS.search(text)
    if status:
        return status.group(1).decode("iso-8859-1")
    raise ValueError(f"Did not find status in {repr(text)}")


class SubstitutionsTooOldException(Exception):
    pass


class BaseSubstitutionParser(HTMLParser):
    REGEX_TITLE = re.compile(r"(\d+.\d+.\d\d\d\d) (\w+), Woche (\w+)")

    def __init__(self, data: dict, current_timestamp: int):
        super().__init__()
        self.data = data
        self.current_timestamp = current_timestamp
        self.day_timestamp = None
        self.day_data = None
        self.has_read_news_heading = False
        self.current_section = ""
        self.current_substitution = []
        self.reached_news = False
        self.is_in_tag = False
        self.is_in_td = False
        self.current_news_format_tag = None
        self.next_site = None
        self.current_day_info = None
        self.news_tag_br = False

    def error(self, message):
        pass

    def _get_attr(self, attrs, name):
        for attr in attrs:
            if attr[0] == name:
                return attr[1]
        return None

    def on_new_substitution_start(self):
        self.current_substitution = []

    def handle_starttag(self, tag, attrs):
        if tag == "td":
            self.is_in_td = True
            if self.current_section == "info-table" and \
                    (self.reached_news or attrs == [("class", "info"), ("colspan", "2")]):
                self.reached_news = True
                self.news_tag_br = False
                self.day_data["news"].append("")
        elif tag == "tr":
            if self.current_section == "substitution-table":
                self.on_new_substitution_start()
        elif tag == "table":
            if len(attrs) == 1 and attrs[0][0] == "class":
                if attrs[0][1] == "info":
                    self.current_section = "info-table"
                elif attrs[0][1] == "mon_list":
                    self.current_section = "substitution-table"
        elif tag == "div":
            if len(attrs) == 1 and attrs[0] == ("class", "mon_title"):
                self.current_section = "title"
        elif tag == "meta":
            if len(attrs) == 2 and attrs[0] == ("http-equiv", "refresh") and attrs[1][0] == "content":
                self.next_site = attrs[1][1].split("URL=")[1]
        elif self.is_in_td and self.current_section == "info-table" and self.reached_news:
            if tag == "br":
                self.news_tag_br = True
            else:
                self.day_data["news"][-1] += "<" + tag + ">"
        self.is_in_tag = True

    def get_current_group(self):
        raise NotImplementedError

    def get_current_substitution(self):
        raise NotImplementedError

    def handle_endtag(self, tag):
        if self.current_section == "substitution-table":
            if tag == "tr" and self.current_substitution:
                group = self.get_current_group()
                substitution = self.get_current_substitution()
                try:
                    if substitution not in self.day_data["substitutions"][group]:
                        self.day_data["substitutions"][group].append(substitution)
                except KeyError:
                    self.day_data["substitutions"][group] = [substitution]
        if tag == "td":
            self.is_in_td = False
        if self.is_in_td and self.current_section == "info-table" and self.reached_news:
            self.day_data["news"][-1] += "</" + tag + ">"
        self.is_in_tag = False

    def handle_data(self, data):
        if self.is_in_tag and self.current_section == "substitution-table":
            self.handle_substitution_data(data)
        elif self.current_section == "info-table":
            if self.is_in_td:
                if not self.reached_news:
                    if self.current_day_info:
                        self.day_data["info"].append((self.current_day_info, data))
                        self.current_day_info = None
                    else:
                        self.current_day_info = data.strip()
                        if self.current_day_info == "Nachrichten zum Tag":
                            self.current_day_info = None
                else:
                    if self.news_tag_br:
                        self.day_data["news"].append(data.strip())
                    else:
                        self.day_data["news"][-1] += data.strip()
        elif self.current_section == "title":
            match = self.REGEX_TITLE.search(data)
            if match:
                date = match.group(1)
                self.day_timestamp = create_date_timestamp(datetime.datetime.strptime(date, "%d.%m.%Y"))
                if self.day_timestamp < self.current_timestamp:
                    raise SubstitutionsTooOldException
                if self.day_timestamp not in self.data:
                    self.day_data = {
                        "date": date,
                        "day_name": match.group(2),
                        "week": match.group(3),
                        "news": [],
                        "info": [],
                        "substitutions": {}
                    }
                    self.data[self.day_timestamp] = self.day_data
                else:
                    self.day_data = self.data[self.day_timestamp]
                self.current_section = None
            else:
                raise ValueError("no date detected in title")

    def handle_substitution_data(self, data):
        if self.is_in_td:
            self.current_substitution.append(data)

    def handle_comment(self, data):
        pass

    def handle_decl(self, data):
        pass

    def close(self):
        super().close()

    def is_last_site(self) -> bool:
        return self.next_site == "subst_001.htm"


class StudentSubstitutionParser(BaseSubstitutionParser):
    def __init__(self, data: dict, current_timestamp: int):
        super().__init__(data, current_timestamp)

    def get_current_group(self):
        return self.current_substitution[0].strip()

    def get_current_substitution(self):
        return StudentSubstitution(*self.current_substitution[1:])


class TeacherSubstitutionParser(BaseSubstitutionParser):
    def __init__(self, data: dict, current_timestamp: int):
        super().__init__(data, current_timestamp)
        self.is_in_strike = False
        self.current_strikes = []

    def get_current_group(self):
        return (self.current_substitution[0].strip(), self.current_strikes[0])

    def get_current_substitution(self):
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
        if self.is_in_td:
            self.current_strikes.append(self.is_in_strike)
            self.current_substitution.append(data)
