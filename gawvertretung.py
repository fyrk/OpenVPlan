#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import base64
import sys
import os

import bot_listener

dir = os.path.dirname(__file__)
os.chdir(dir)
sys.path.append(os.path.join(dir, "sitepackages/"))
import json
import logging
import time
import hashlib
import re
import datetime
import threading
import urllib.request
import urllib.error
import urllib.parse
from html.parser import HTMLParser
from collections import OrderedDict


class Snippets:
    ABSENT_CLASSES = '''<span class="heading absent-classes">Abwesende Klassen: </span>"
<span class="info-text">{}</span>'''

    ABSENT_TEACHERS = '''<span class="heading absent-teachers">Abwesende Lehrer: </span>
<span class="info-text">{}</span>'''

    DAY_CONTAINER = '''<div class="container">
	{day_info}
	{substitutions}
</div>'''

    DAY_INFO_ALL = '''<div><span class="day-name">{day_name}</span><span class="date">, {date}</span></div>
<div class="parted">
	<div class="half">
		<div class="week">Woche {week}</div>{news}
	</div>
	<div class="half">{absent_teachers}{absent_classes}
	</div>
</div>'''

    DAY_INFO_ONLY_ABSENT = '''<div><span class="day-name">{day_name}</span><span class="date">, {date}</span></div>
<div class="week">Woche {week}</div>
{absent_teachers}{absent_classes}'''

    INDEX = '''<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
<link rel="icon" sizes="any" type="image/svg+xml" href="/favicon.svg">
<link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">
<link rel="icon" type="image/png" sizes="32x32" href="/favicon-32x32.png">
<link rel="icon" type="image/png" sizes="16x16" href="/favicon-16x16.png">
<link rel="manifest" href="/site.webmanifest">
<link rel="mask-icon" href="/safari-pinned-tab.svg" color="#e67b10">
<meta name="apple-mobile-web-app-title" content="GaW VPlan">
<meta name="application-name" content="GaW VPlan">
<meta name="msapplication-TileColor" content="#00a300">
<meta name="theme-color" content="#e67b10">
<title>Vertretungsplan Gymnasium am Wall Verden</title>
<meta name="description" content="Vertretungsplan für das Gymnasium am Wall Verden">
<meta name="keywords" content="Gymnasium am Wall, Vertretung, Vertretungsplan, Verden, Schule, Ausfall, Unterricht">

<meta property="og:type" content="website">
<meta property="og:url" content="gawvertretung.florianraediker.de">
<meta property="og:title" content="Vertretungsplan Gymnasium am Wall Verden">
<meta property="og:description" content="Vertretungsplan für das Gymnasium am Wall Verden">

<link rel="stylesheet" href="/style/main.css">
<noscript>
<link rel="stylesheet" href="/style/noscript.css">
</noscript>
</head>
<body>
<div id="content">
<div class="container" id="title-bar">
	Vertretungsplan Gymnasium am Wall Verden
</div>
{}
<div class="container" id="status-container">
	Stand: {status}
</div>
{}
</div>
<footer>
<p id="telegram-info">
    Der Telegram-Bot <a href="https://t.me/GaWVertretungBot{telegram_link}" target="_blank">@GaWVertretungBot</a> informiert automatisch über Vertretungen. 
</p>
<p>
	Dies ist eine Alternative zum originalen Vertretungsplan unter <a href="https://gaw-verden.de/images/vertretung/klassen/subst_001.htm" target="_blank">gaw-verden.de</a>. Alle Angaben ohne Gewähr.
</p>
<p>
	Programmiert von Florian Rädiker.
</p>
</footer>
<script src="/js/main.js"></script>
</body>
</html>'''

    ERROR = '''<!DOCTYPE html>
<html lang="de">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, maximum-scale=1">
<link rel="icon" sizes="any" type="image/svg+xml" href="/favicon.svg">
<link rel="apple-touch-icon" sizes="180x180" href="/apple-touch-icon.png">
<link rel="icon" type="image/png" sizes="32x32" href="/favicon-32x32.png">
<link rel="icon" type="image/png" sizes="16x16" href="/favicon-16x16.png">
<link rel="manifest" href="/site.webmanifest">
<link rel="mask-icon" href="/safari-pinned-tab.svg" color="#e67b10">
<meta name="apple-mobile-web-app-title" content="GaW VPlan">
<meta name="application-name" content="GaW VPlan">
<meta name="msapplication-TileColor" content="#00a300">
<meta name="theme-color" content="#e67b10">
<title>Vertretungsplan Gymnasium am Wall Verden</title>
<meta name="description" content="Vertretungsplan für das Gymnasium am Wall Verden">
<meta name="keywords" content="Gymnasium am Wall, Vertretung, Vertretungsplan, Verden, Schule, Ausfall, Unterricht">

<meta property="og:type" content="website">
<meta property="og:url" content="gawvertretung.florianraediker.de">
<meta property="og:title" content="Vertretungsplan Gymnasium am Wall Verden">
<meta property="og:description" content="Vertretungsplan für das Gymnasium am Wall Verden">

<link rel="stylesheet" href="/style/main.css">
<link rel="icon" href="/favicon.ico">
</head>
<body>
<div id="content">
	<div class="container" id="title-bar">
		Vertretungsplan Gymnasium am Wall Verden
	</div>
	<div class="container">
		<h1>Ein Fehler ist aufgetreten</h1>
		Der <a href="https://gaw-verden.de/images/vertretung/klassen/subst_001.htm">originale Vertretungsplan</a> konnte nicht eingelesen werden.
	</div>
</div>
<footer>
	<p>
		Dies ist eine Alternative zum originalen Vertretungsplan unter <a href="https://gaw-verden.de/images/vertretung/klassen/subst_001.htm">gaw-verden.de</a>. Alle Angaben ohne Gewähr.
	</p>
	<p>
		Programmiert von Florian Rädiker.
	</p>
</footer>
</body>
</html>'''

    NEWS = '''<span class="heading news">Nachrichten: </span>
<span class="news">{}</span>'''

    NO_SUBSTITUTIONS = '''<div class="selected-classes">Es gibt keine Vertretungen</div>'''

    NO_SUBSTITUTIONS_RESET_CLASSES = '''<div class="selected-classes">Es gibt keine Vertretungen für die Klasse(n) <i>{}</i>. <a href="/">Alle Klassen</a></div>'''

    NOTICE_CLASSES_ARE_SELECTED = '''<div class="selected-classes">Es werden Vertretungen für <i>{}</i> angezeigt. <a href="/">Alle Klassen</a></div>'''

    SELECT_CLASSES = '''<div class="container" id="select-classes-container">
	<form action="javascript:onSetClassesSelection()" autocomplete="off">
		<label for="select-classes-input" class="select-classes-label">Alle Klassen, die angezeigt werden sollen, durch Kommata getrennt eingeben: </label>
		<span id="select-classes-input-wrapper">
			<input type="text" id="select-classes-input" autofocus placeholder="z.B. 6A, 11C">
			<button type="submit" class="button">OK</button>
		</span>
	</form>
</div>
<script>
	const container = document.getElementById("select-classes-container");
	const classesInput = document.getElementById("select-classes-input");
	container.classList.add("visible");
	function onSetClassesSelection() {{
		const searchParams = new URLSearchParams(window.location.search);
		searchParams.set("classes", classesInput.value);
		window.location = window.location.pathname + "?classes=" + classesInput.value.toString();
	}}
</script>'''

    SUBSTITUTION_ROW = '''<tr class="{lesson_num}"><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>'''

    SUBSTITUTION_ROW_FIRST = '''<tr class="class-start {lesson_num}"><td rowspan="{}" class="class-name">{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td><td>{}</td></tr>'''

    SUBSTITUTION_TABLE = '''<div class="scroll-table">
	<table class="substitutions">
		<thead>
			<tr>
				<td>Klasse(n)</td>
				<td>Lehrer</td>
				<td>Vertreter</td>
				<td>Stunde</td>
				<td>Fach</td>
				<td>Raum</td>
				<td>Vertr. von</td>
				<td>Hinweistext</td>
			</tr>
		</thead>
		<tbody>
{}
		</tbody>
	</table>
</div>'''


REGEX_STATUS = re.compile(b"Stand: (\d\d\.\d\d\.\d\d\d\d \d\d:\d\d)")

REGEX_CLASS = re.compile(r"(?:\D|\A)(\d{1,3})([A-Za-z]*)(?:\D|\Z)")


def sort_classes(class_name):
    matches = REGEX_CLASS.search(class_name)
    if matches:
        return int(matches.group(1)), matches.group(2)
    if "<" in class_name:
        matches = re.search(r">(.*?)<", class_name)
        if matches:
            return 0, matches.group(1)
    return 0, class_name


def split_class_name(class_name):
    matches = REGEX_CLASS.search(class_name)
    if matches:
        return matches.group(1), matches.group(2)
    return "", class_name


def get_status_string(text):
    status = REGEX_STATUS.search(text)
    if status:
        return status.group(1).decode("iso-8859-1")
    raise ValueError


def create_date_timestamp(date):
    return int(datetime.datetime.strptime(date, "%d.%m.%Y").timestamp())


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
                                self.current_day_info = "absent_teachers"
                            elif "Abwesende Klassen" in data:
                                self.current_day_info = "absent_classes"
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
                                self.day_data[self.current_day_info].extend(data.split(", "))
                            else:
                                self.day_data[self.current_day_info] = data.split(", ")
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


def create_data(first_site):
    new_data = {}
    current_timestamp = create_date_timestamp(datetime.datetime.now().strftime("%d.%m.%Y"))
    parser = SubstitutionParser(new_data, current_timestamp)
    try:
        parser.feed(first_site.decode("iso-8859-1"))
        parser.close()
    except ValueError:
        # return data
        pass
    site_num = 2
    while True:
        logger.debug("REQUEST subst_{:03}.htm".format(site_num))
        try:
            site_request = urllib.request.urlopen(
                "https://gaw-verden.de/images/vertretung/klassen/subst_{:03}.htm".format(site_num))
        except urllib.error.HTTPError:
            logger.debug("ERROR 404")
            break
        parser.reset()
        try:
            parser.feed(site_request.read().decode("iso-8859-1"))
            parser.close()
        except ValueError:
            pass
        if parser.next_site == "subst_001.htm":
            logger.debug("next site is 'subst_001.htm'")
            break
        site_num += 1
    return new_data


def create_day_container(day, substitutions):
    absent_teachers = (Snippets.ABSENT_TEACHERS.format(", ".join(sorted(day["absent_teachers"])))
                       if "absent_teachers" in day else "")
    absent_classes = (Snippets.ABSENT_CLASSES.format(", ".join(sorted(day["absent_classes"])))
                      if "absent_classes" in day else "")
    if "news" in day:
        day_info = Snippets.DAY_INFO_ALL.format(
            day_name=day["day_name"],
            date=day["date"],
            week=day["week"],
            news=Snippets.NEWS.format(day["news"]),
            absent_teachers=absent_teachers,
            absent_classes=absent_classes
        )
    else:
        day_info = Snippets.DAY_INFO_ONLY_ABSENT.format(
            day_name=day["day_name"],
            date=day["date"],
            week=day["week"],
            absent_teachers=absent_teachers,
            absent_classes=absent_classes
        )
    return Snippets.DAY_CONTAINER.format(
        day_info=day_info,
        substitutions=substitutions
    )


REGEX_NUMBERS = re.compile(r"\d*")


def get_lesson_num(lesson_string):
    try:
        return "lesson" + str(max(int(num.group(0))
                                  for num in REGEX_NUMBERS.finditer(lesson_string) if num.group(0) != ""))
    except:
        logger.exception("Could not determine lesson number for '{}'".format(lesson_string))
        return ""


def create_site_and_send_notifications(new_data, status_string):
    global sent_substitutions, new_sent_substitutions
    with open("data/bot_users.json", "r") as f:
        bot_users = json.load(f)
    with open("data/sent_substitutions.json", "r") as f:
        sent_substitutions = json.load(f)
    new_sent_substitutions = set()

    containers = ""
    current_timestamp = create_date_timestamp(datetime.datetime.now().strftime("%d.%m.%Y"))
    i = 0
    for day_timestamp, day in new_data.items():
        print(day_timestamp, day)
        if day_timestamp >= current_timestamp:
            i += 1
            day["substitutions"] = OrderedDict(sorted(day["substitutions"].items(), key=lambda s: sort_classes(s[0])))
            substitution_rows = ""
            for class_name, class_substitutions in day["substitutions"].items():
                substitution_rows += Snippets.SUBSTITUTION_ROW_FIRST.format(len(class_substitutions), class_name,
                                                                            *class_substitutions[0],
                                                                            lesson_num=get_lesson_num(
                                                                                class_substitutions[0][
                                                                                    2]) if i == 1 else "")
                send_substitution_notification(bot_users, day_timestamp, day, class_name, class_substitutions)
                for substitution in class_substitutions[1:]:
                    substitution_rows += Snippets.SUBSTITUTION_ROW.format(*substitution,
                                                                          lesson_num=get_lesson_num(
                                                                              substitution[2]) if i == 1 else "")
            if substitution_rows:
                substitutions = Snippets.SUBSTITUTION_TABLE.format(substitution_rows)
            else:
                substitutions = Snippets.NO_SUBSTITUTIONS
            containers += create_day_container(day, substitutions)
    sent_substitutions.extend(new_sent_substitutions)
    if len(sent_substitutions) > 200:
        sent_substitutions = sent_substitutions[(len(sent_substitutions) - 200):]
    with open("data/sent_substitutions.json", "w") as f:
        json.dump(sent_substitutions, f)
    return Snippets.INDEX.format(Snippets.SELECT_CLASSES, containers, status=status_string, telegram_link="")


def send_substitution_notification(bot_users, day_timestamp, day, class_name, substitutions):
    try:
        global bot, data, sent_substitutions, new_sent_substitutions
        for user_id, user_data in bot_users.items():
            if "selected-classes" in user_data:
                selected_classes_split = [split_class_name(name) for name in user_data["selected-classes"]]
                substitutions_for_sending = []
                for substitution in substitutions:
                    substitution_hash = hashlib.sha1(
                        ".".join((str(day_timestamp), class_name, *substitution)).encode()).hexdigest()
                    if substitution_hash not in sent_substitutions:
                        new_sent_substitutions.add(substitution_hash)
                        if any(do_class_names_match(class_name, selected_name)
                                for selected_name in selected_classes_split):
                            substitutions_for_sending.append(substitution)
                if substitutions_for_sending:
                    message = '''Vertretungen für {}, {}, Woche {}: 
Klasse {}: \n'''.format(day["day_name"], day["date"], day["week"], class_name)
                    if "send-type" not in user_data or user_data["send-type"] == "text":
                        for substitution in substitutions_for_sending:
                            if "---" in substitution[1] and "---" in substitution[3] and "---" in substitution[4]:
                                if substitution[0].strip():
                                    lehrer = "bei {} ".format(substitution[0])
                                else:
                                    lehrer = ""
                                message += "Die {}. Stunde {}fällt aus".format(substitution[2], lehrer)
                            elif substitution[0] == substitution[1]:
                                if substitution[0].strip():
                                    lehrer = "bei {} ".format(substitution[0])
                                else:
                                    lehrer = ""
                                if substitution[3].strip():
                                    fach = "{} ".format(substitution[3])
                                else:
                                    fach = ""
                                message += "Die {}. Stunde {}{}findet in {} statt".format(substitution[2], fach, lehrer,
                                                                                          substitution[4])
                            else:
                                if substitution[0].strip():
                                    lehrer = "von {} ".format(substitution[0])
                                else:
                                    lehrer = ""
                                if substitution[3].strip():
                                    fach = "{} ".format(substitution[3])
                                else:
                                    fach = ""
                                if substitution[1].strip():
                                    vertreter = "durch {} ".format(substitution[1])
                                else:
                                    vertreter = ""
                                message += "Die {}. Stunde {}{}wird {}in {} vertreten".format(substitution[2], fach,
                                                                                              lehrer, vertreter,
                                                                                              substitution[4])
                            if substitution[5].strip() and substitution[5].strip() != "&nbsp;":
                                if substitution[6].strip() and substitution[6].strip() != "&nbsp;":
                                    message += " (Vertr. von {}, {})".format(substitution[5], substitution[6])
                                else:
                                    message += " (Vertr. von {})".format(substitution[5])
                            else:
                                if substitution[6].strip() and substitution[6].strip() != "&nbsp;":
                                    message += " ({})".format(substitution[6])
                            message += ".\n"
                    else:
                        lengths = [1, 1, 1, 1, 1, 2, 1]
                        for s in substitutions_for_sending:
                            for i in range(7):
                                length = len(s[i])
                                if length > lengths[i]:
                                    lengths[i] = length

                        message += '<pre>| {:^{}} | {:^{}} | {:^{}} | ' \
                                   '{:^{}} | {:^{}} | {:^{}} | ' \
                                   '{:^{}} |\n'.format("L", lengths[0], "V", lengths[1], "S", lengths[2],
                                                                    "F", lengths[3], "R", lengths[4], "Vv", lengths[5],
                                                                    "H", lengths[6])
                        for substitution in substitutions_for_sending:
                            message += "| {:^{}} | {:^{}} | " \
                                       "{:^{}} | {:^{}} | " \
                                       "{:^{}} | {:^{}} | " \
                                       "{:^{}} |\n".format(substitution[0], lengths[0],
                                                           substitution[1], lengths[1],
                                                           substitution[2], lengths[2],
                                                           substitution[3], lengths[3],
                                                           substitution[4], lengths[4],
                                                           substitution[5], lengths[5],
                                                           substitution[6], lengths[6],
                                                           )
                        message += "</pre>"
                    bot.send_message(int(user_id), message.strip(), parse_mode="html")
    except Exception:
        logger.exception("Sending substitution notifications failed")


def create_site(data, status_string):
    containers = ""
    current_timestamp = create_date_timestamp(datetime.datetime.now().strftime("%d.%m.%Y"))
    i = 0
    for day_timestamp, day in data.items():
        print(day_timestamp, day)
        if day_timestamp >= current_timestamp:
            i += 1
            day["substitutions"] = OrderedDict(sorted(day["substitutions"].items(), key=lambda s: sort_classes(s[0])))
            substitution_rows = ""
            for class_name, class_substitutions in day["substitutions"].items():
                substitution_rows += Snippets.SUBSTITUTION_ROW_FIRST.format(len(class_substitutions), class_name,
                                                                            *class_substitutions[0],
                                                                            lesson_num=get_lesson_num(
                                                                                class_substitutions[0][
                                                                                    2]) if i == 1 else "")
                for substitution in class_substitutions[1:]:
                    substitution_rows += Snippets.SUBSTITUTION_ROW.format(*substitution,
                                                                          lesson_num=get_lesson_num(
                                                                              substitution[2]) if i == 1 else "")
            if substitution_rows:
                substitutions = Snippets.SUBSTITUTION_TABLE.format(substitution_rows)
            else:
                substitutions = Snippets.NO_SUBSTITUTIONS
            containers += create_day_container(day, substitutions)
    return Snippets.INDEX.format(Snippets.SELECT_CLASSES, containers, status=status_string, telegram_link="")


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
                    substitution_rows += Snippets.SUBSTITUTION_ROW_FIRST.format(len(class_substitutions),
                                                                                class_name,
                                                                                *class_substitutions[0],
                                                                                lesson_num=get_lesson_num(
                                                                                    class_substitutions[0][
                                                                                        2]) if i == 1 else "")
                    for substitution in class_substitutions[1:]:
                        substitution_rows += Snippets.SUBSTITUTION_ROW.format(*substitution,
                                                                              lesson_num=get_lesson_num(
                                                                                  substitution[
                                                                                      2]) if i == 1 else "")
            if substitution_rows:
                substitutions = Snippets.SUBSTITUTION_TABLE.format(
                    substitution_rows) + Snippets.NOTICE_CLASSES_ARE_SELECTED.format(selected_classes_string)
            else:
                substitutions = Snippets.NO_SUBSTITUTIONS_RESET_CLASSES.format(selected_classes_string)
            containers += create_day_container(day, substitutions)
    return Snippets.INDEX.format("", containers, status=status_string,
                                 telegram_link="?start=" +
                                               base64.urlsafe_b64encode(selected_classes_string.encode("utf-8"))
                                 .replace(b"=", b"").decode("utf-8"))


last_status = datetime.datetime.fromtimestamp(0)
data = {}
index_site = ""
status_string = ""
sent_substitutions = []
new_sent_substitutions = set()


def get_main_page(storage):
    global last_status, data, index_site, status_string, sent_substitutions
    logger.debug("Requesting subst_001.htm ...")
    t1 = time.perf_counter()
    with urllib.request.urlopen("https://gaw-verden.de/images/vertretung/klassen/subst_001.htm") as site:
        text = site.read()
    t2 = time.perf_counter()
    logger.debug("Got answer in {:.3f}".format(t2 - t1))

    status_string = get_status_string(text)
    status = datetime.datetime.strptime(status_string, "%d.%m.%Y %H:%M")

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
        logger.debug("Creating site and sending bot notifications...")
        t1 = time.perf_counter()
        index_site = create_site_and_send_notifications(new_data, status_string)
        t2 = time.perf_counter()
        data = new_data
        logger.debug("Site created and bot notifications sent in {:.3f}".format(t2 - t1))
        last_status = status
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


def app(environ, start_response):
    if environ["PATH_INFO"] == "/":
        storage = urllib.parse.parse_qs(environ["QUERY_STRING"])
        start_response("200 OK", [("Content-Type", "text/html; charset=utf-8")])
        return [get_main_page(storage).encode("utf-8")]


logger = logging.getLogger()
logger.setLevel(logging.DEBUG)
log_formatter = logging.Formatter("{asctime} [{levelname:^8}]: {message}", "%Y.%m.%e %H:%M:%S", style="{")
file_logger = logging.FileHandler(time.strftime("logs/log-%Y.%m.%e_%H-%M-%S.txt"))
file_logger.setFormatter(log_formatter)
logger.addHandler(file_logger)
stdout_logger = logging.StreamHandler(sys.stdout)
stdout_logger.setFormatter(log_formatter)
logger.addHandler(stdout_logger)

logger.info("Starting bot")
with open("data/secret.json", "r") as f:
    bot = bot_listener.start_bot(json.load(f)["token"])
logger.info("Bot started")
bot_thread = threading.Thread(target=bot.infinity_polling, daemon=True)
bot_thread.start()
