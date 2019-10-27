#!/usr/bin/env python3.8
# -*- coding: utf-8 -*-
import asyncio
import base64
import os
import pickle
import sys

sys.path.append("/home/pi/gawvertretung-python-venv/lib/python3.8/site-packages/")
sys.path.append("/home/pi/gawvertretung-website/")

os.chdir(os.path.dirname(__file__))

import time
import urllib.request
import urllib.error
import urllib.parse
from html.parser import HTMLParser
from collections import OrderedDict

import aiohttp

from substitution_utils import *
from logging_tool import create_logger


class Snippets:
    __files = {}

    @staticmethod
    def load():
        with open("snippets/_base.html", "r") as f:
            base = f.read()
        if base.startswith("<!--ignore: "):
            first_line, base = base[12:].split("\n", 1)
            base_ignore_keys = {key.strip(): "{" + key.strip() + "}" for key in first_line[:-3].split(",")}
        else:
            base_ignore_keys = {}
        Snippets.__files = {}
        for filename_ext in list(os.walk("snippets"))[0][2]:
            if filename_ext.endswith(".html") and not filename_ext == "_base.html" and \
                    not filename_ext.endswith(".styles.html") and not filename_ext.startswith("."):
                with open("snippets/" + filename_ext, "r") as f:
                    filename = filename_ext[:-5]
                    snippet = f.read()
                if snippet.startswith("<!--_base-->\n"):
                    snippet = snippet[13:]
                    filename_styles = "snippets/" + filename + "_styles.html"
                    if os.path.exists(filename_styles):
                        with open(filename_styles, "r") as f:
                            styles = f.read()
                    else:
                        styles = ""
                    keys = base_ignore_keys.copy()
                    if snippet.startswith("<!--keys: "):
                        add_keys, snippet = snippet[10:].split("\n", 1)
                        for key_value in add_keys[:-3].split(","):
                            key, value = key_value.split("=", 1)
                            key = key.strip()
                            value = value.strip()
                            keys[key] = value
                    Snippets.__files[filename] = base.format(content=snippet, styles=styles, **keys)
                else:
                    Snippets.__files[filename] = snippet

    @staticmethod
    def get(name):
        try:
            return Snippets.__files[name]
        except KeyError:
            raise ValueError("Did not find snippet '{}'".format(name))


Snippets.load()


class SubstitutionParser(HTMLParser):
    REGEX_TITLE = re.compile(r"(\d+.\d+.\d\d\d\d) (\w+), Woche (\w+)")

    def __init__(self, data, current_timestamp):
        super().__init__()
        self.data = data
        self.current_timestamp = current_timestamp
        self._reset()

    def _reset(self):
        self.day_timestamp = None
        self.day_data = None
        self.has_read_news_heading = False
        self.current_section = ""
        self.last_tag = ""
        self.current_tag = ""
        self.current_substitution = []
        self.current_day_info = None
        self.is_in_tag = False
        self.next_site = None

    def error(self, message):
        pass

    def reset(self):
        super().reset()
        self._reset()

    def _get_attr(self, attrs, name):
        for attr in attrs:
            if attr[0] == name:
                return attr[1]
        return None

    def handle_starttag(self, tag, attrs):
        if tag == "br":
            if self.current_section == "info":
                if self.current_tag == "td":
                    if self.current_day_info == "news":
                        if "news" in self.day_data["news"]:
                            self.day_data["news"] += "<br>"
                        else:
                            self.day_data["news"] = "<br>"
        elif tag == "meta":
            if len(attrs) == 2 and attrs[0] == ("http-equiv", "refresh") and attrs[1][0] == "content":
                self.next_site = attrs[1][1].split("URL=")[1]
        else:
            if tag == "tr":
                if self.current_section == "mon_list":
                    self.current_substitution = []
            elif tag == "table":
                section = self._get_attr(attrs, "class")
                if section == "mon_title" or section == "info" or section == "mon_list":
                    self.current_section = section
            elif tag == "div":
                if self._get_attr(attrs, "class") == "mon_title":
                    self.current_section = "mon_title"
            self.last_tag = self.current_tag
            self.current_tag = tag
            self.is_in_tag = True

    def handle_endtag(self, tag):
        if self.current_section == "mon_list":
            if tag == "tr" and self.current_substitution:
                try:
                    if self.current_substitution[1:] not in \
                            self.day_data["substitutions"][self.current_substitution[0]]:
                        self.day_data["substitutions"][self.current_substitution[0]].append(
                            self.current_substitution[1:])
                except KeyError:
                    self.day_data["substitutions"][self.current_substitution[0]] = [self.current_substitution[1:]]
        self.is_in_tag = False

    def handle_data(self, data):
        if self.is_in_tag:
            if self.current_section == "mon_title":
                match = self.REGEX_TITLE.search(data)
                if match:
                    date = match.group(1)
                    self.day_timestamp = create_date_timestamp(date)
                    if self.day_timestamp < self.current_timestamp:
                        raise ValueError
                    if self.day_timestamp not in self.data:
                        self.day_data = {
                            "date": date,
                            "day_name": match.group(2),
                            "week": match.group(3),
                            "substitutions": {}
                        }
                        self.data[self.day_timestamp] = self.day_data
                    else:
                        self.day_data = self.data[self.day_timestamp]
                else:
                    raise ValueError
            elif self.current_section == "info":
                if self.current_tag == "td":
                    if not self.current_day_info:
                        if "Nachrichten zum Tag" not in data:
                            if "Abwesende Lehrer" in data:
                                self.current_day_info = "absent-teachers"
                            elif "Abwesende Klassen" in data:
                                self.current_day_info = "absent-classes"
                            else:
                                if "news" in self.day_data:
                                    self.day_data["news"] += "<br>" + data
                                    logger.debug("add news data " + data)
                                else:
                                    self.day_data["news"] = data
                                    logger.debug("news data " + data)
                                self.current_day_info = None
                    else:
                        if self.current_day_info:
                            if self.current_day_info in self.day_data:
                                self.day_data[self.current_day_info] += ", " + data
                            else:
                                self.day_data[self.current_day_info] = data
                            self.current_day_info = None
            elif self.current_section == "mon_list":
                if self.current_tag == "td" or (self.current_tag == "span" and self.last_tag == "td"):
                    self.current_substitution.append(data)

    def handle_comment(self, data):
        pass

    def handle_decl(self, data):
        pass

    def close(self):
        super().close()


async def get_data_from_site(new_data, current_timestamp, session: aiohttp.ClientSession, site_num):
    logger.info("REQUEST subst_" + str(site_num) + ".htm")
    async with session.get("https://gaw-verden.de/images/vertretung/klassen/subst_{:03}.htm".format(site_num)) as \
            response:
        response.raise_for_status()
        response_data = await response.text("iso-8859-1")
        parser = SubstitutionParser(new_data, current_timestamp)
        try:
            parser.feed(response_data)
            parser.close()
        except ValueError:
            pass
        return parser.next_site == "subst_001.htm"


async def create_data_async(new_data, current_timestamp):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    session = aiohttp.ClientSession()
    i = 2
    while True:
        if True in await asyncio.gather(
                *(get_data_from_site(new_data, current_timestamp, session, site_num) for site_num in range(i, i + 4))):
            await session.close()
            for day_timestamp, day in new_data.items():
                if "absent-teachers" in day:
                    day["absent-teachers"] = ", ".join(sorted(day["absent-teachers"].split(", ")))
                if "absent-classes" in day:
                    day["absent-classes"] = ", ".join(sorted(day["absent-classes"].split(", "), key=sort_classes))
            return new_data
        i += 4


def create_data(first_site):
    new_data = {}
    current_timestamp = create_date_timestamp(datetime.datetime.now().strftime("%d.%m.%Y"))
    parser = SubstitutionParser(new_data, current_timestamp)
    try:
        parser.feed(first_site.decode("iso-8859-1"))
        parser.close()
    except ValueError:
        pass
    if parser.next_site == "subst_001.htm":
        return new_data
    return asyncio.run(create_data_async(new_data, current_timestamp))


def create_day_container(day, substitutions):
    absent_teachers = (Snippets.get("absent-teachers").format(day["absent-teachers"])
                       if "absent-teachers" in day else "")
    absent_classes = (Snippets.get("absent-classes").format(day["absent-classes"]) if "absent-classes" in day else "")
    if "news" in day:
        day_info = Snippets.get("day-info-all").format(
            day_name=day["day_name"],
            date=day["date"],
            week=day["week"],
            news=Snippets.get("news").format(day["news"]),
            absent_teachers=absent_teachers,
            absent_classes=absent_classes
        )
    else:
        day_info = Snippets.get("day-info-only-absent").format(
            day_name=day["day_name"],
            date=day["date"],
            week=day["week"],
            absent_teachers=absent_teachers,
            absent_classes=absent_classes
        )
    return Snippets.get("day-container").format(
        day_info=day_info,
        substitutions=substitutions
    )


REGEX_NUMBERS = re.compile(r"\d*")


def get_lesson_num(lesson_string):
    try:
        return "lesson" + str(max(int(num.group(0))
                                  for num in REGEX_NUMBERS.finditer(lesson_string) if num.group(0) != ""))
    except Exception:
        logger.exception("Could not determine lesson number for '{}'".format(lesson_string))
        return ""


def create_site(data, status_string):
    containers = ""
    current_timestamp = create_date_timestamp(datetime.datetime.now().strftime("%d.%m.%Y"))
    i = 0
    for day_timestamp, day in data.items():
        if day_timestamp >= current_timestamp:
            i += 1
            day["substitutions"] = OrderedDict(sorted(day["substitutions"].items(), key=lambda s: sort_classes(s[0])))
            substitution_rows = ""
            for class_name, class_substitutions in day["substitutions"].items():
                substitution_rows += Snippets.get("substitution-row-first") \
                    .format(len(class_substitutions), class_name, *class_substitutions[0],
                            lesson_num=get_lesson_num(class_substitutions[0][2]) if i == 1 else "")
                for substitution in class_substitutions[1:]:
                    substitution_rows += Snippets.get("substitution-row") \
                        .format(*substitution, lesson_num=get_lesson_num(substitution[2]) if i == 1 else "")
            if substitution_rows:
                substitutions = Snippets.get("substitution-table").format(substitution_rows)
            else:
                substitutions = Snippets.get("no-substitutions")
            containers += create_day_container(day, substitutions)
    return Snippets.get("index").format(Snippets.get("select-classes"), containers, status=status_string,
                                        telegram_link="")


def do_class_names_match(class_name, selected_class):
    class_name = class_name.lower()
    return selected_class[0].lower() in class_name and selected_class[1].lower() in class_name


def create_site_with_selected(data, selected_classes, status_string):
    selected_classes_string = ", ".join(selected_classes)
    selected_classes_split = [split_class_name(name) for name in selected_classes]
    containers = ""
    current_timestamp = create_date_timestamp(datetime.datetime.now().strftime("%d.%m.%Y"))
    i = 0
    for day_timestamp, day in data.items():
        if day_timestamp >= current_timestamp:
            i += 1
            substitution_rows = ""
            for class_name, class_substitutions in day["substitutions"].items():
                if any(do_class_names_match(class_name, selected_name) for selected_name in selected_classes_split):
                    substitution_rows += Snippets.get("substitution-row-first") \
                        .format(len(class_substitutions), class_name, *class_substitutions[0],
                                lesson_num=get_lesson_num(class_substitutions[0][2]) if i == 1 else "")
                    for substitution in class_substitutions[1:]:
                        substitution_rows += Snippets.get("substitution-row") \
                            .format(*substitution, lesson_num=get_lesson_num(substitution[2]) if i == 1 else "")
            if substitution_rows:
                substitutions = Snippets.get("substitution-table").format(
                    substitution_rows) + Snippets.get("notice-classes-are-selected").format(selected_classes_string)
            else:
                substitutions = Snippets.get("no-substitutions-reset-classes").format(selected_classes_string)
            containers += create_day_container(day, substitutions)
    return Snippets.get("index").format("", containers, status=status_string,
                                        telegram_link="?start=" + base64.urlsafe_b64encode(
                                            selected_classes_string.encode("utf-8")).replace(b"=", b"").decode("utf-8"))


last_status = datetime.datetime.fromtimestamp(0)
data = {}
index_site = ""
status_string = ""


def get_main_page(storage):
    global last_status, data, index_site, status_string
    logger.debug("Requesting subst_001.htm ...")
    t1 = time.perf_counter()
    with urllib.request.urlopen("https://gaw-verden.de/images/vertretung/klassen/subst_001.htm") as site:
        text = site.read()
    t2 = time.perf_counter()
    logger.debug("Got answer in {:.3f}".format(t2 - t1))

    status_string = get_status_string(text)
    status = datetime.datetime.strptime(status_string, "%d.%m.%Y %H:%M")
    logger.debug("Status is '" + status_string + "', " + str(status))

    selected_classes = None
    if "classes" in storage:
        if storage["classes"] != "":
            selected_classes = []
            for selected_class in "".join(storage["classes"][0].split()).split(","):
                if selected_class not in selected_classes:
                    selected_classes.append(selected_class)

    if status > last_status:
        logger.debug("Creating new data...")
        t1 = time.perf_counter()
        new_data = create_data(text)
        t2 = time.perf_counter()
        logger.debug("New data created in {:.3f}".format(t2 - t1))
        logger.debug("Creating site...")
        t1 = time.perf_counter()
        index_site = create_site(new_data, status_string)
        t2 = time.perf_counter()
        data = new_data
        logger.debug("Site created in {:.3f}".format(t2 - t1))
        last_status = status
        with open("data/substitutions/substitutions.pickle", "wb") as f:
            pickle.dump((last_status, new_data), f)
        if not selected_classes:
            return index_site
    elif not selected_classes:
        today = datetime.datetime.now()
        if today.date() > last_status.date():  # _date:
            logger.debug("new day, but no update yet")
            index_site = create_site(data, status_string)
            last_status = today
            return index_site

    if selected_classes:
        return create_site_with_selected(data, selected_classes, status_string)
    return index_site


def application(environ, start_response):
    if environ["PATH_INFO"] == "/":
        storage = urllib.parse.parse_qs(environ["QUERY_STRING"])
        start_response("200 OK", [("Content-Type", "text/html; charset=utf-8")])
        return [get_main_page(storage).encode("utf-8")]
    if environ["PATH_INFO"] == "/api/last-status":
        get_main_page({})
        start_response("200 OK", [("Content-Type", "text/text; charset=utf-8")])
        return [status_string.encode("utf-8")]
    start_response("400 NOT FOUND", [("Content-Type", "text/html; charset=utf-8")])
    return [Snippets.get("error-404").encode("utf-8")]


if __name__ == "__main__" or "wsgi" in __name__:
    logger = create_logger("website")
else:
    logger = None
