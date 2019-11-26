import asyncio
import datetime
import hashlib
import json
import logging
from collections import deque, namedtuple

from bot.db.base import DatabaseChat
from website.substitution_utils import create_date_timestamp

logger = logging.getLogger()

Day = namedtuple("Day", ("date_info", "info", "substitutions"))
DayInfo = namedtuple("DayInfo", ("news", "absent_classes", "absent_teachers"))


class BaseMessageSender:
    def __init__(self, bot, sent_messages_file):
        self.bot = bot
        self.sent_messages_file = sent_messages_file
        with open(sent_messages_file, "r") as f:
            sent_messages = json.load(f)
        self.sent_substitutions = deque(sent_messages["substitutions"], maxlen=200)
        self.sent_news = deque(sent_messages["news"], maxlen=20)
        self.sent_absent_classes = deque(sent_messages["absent-classes"], maxlen=20)
        self.sent_absent_teachers = deque(sent_messages["absent-teachers"], maxlen=20)

    def save_sent_messages(self):
        with open(self.sent_messages_file, "w") as f:
            json.dump({
                "news": list(self.sent_news),
                "absent-classes": list(self.sent_absent_classes),
                "absent-teachers": list(self.sent_absent_teachers),
                "substitutions": list(self.sent_substitutions)
            }, f)

    async def send_messages(self, data):
        current_timestamp = create_date_timestamp(datetime.datetime.now().strftime("%d.%m.%Y"))
        days = {day_timestamp: Day(self._build_day_date(day),
                                   self._build_day_info(day),
                                   self._build_substitutions(day["substitutions"], day["date"]))
                for day_timestamp, day in data.items()
                if day_timestamp >= current_timestamp}
        for day_timestamp, day in days.items():
            await asyncio.gather(*(self._send_message_to(chat, day_timestamp, day)
                                   for chat in self.bot.chats.all_chats()))

    async def _send_message_to(self, chat: DatabaseChat, day_timestamp, day: Day):
        raise NotImplementedError

    def _build_message_info_text(self, chat, day):
        message = ""
        if chat.send_news and day.info.news:
            message += "Nachrichten: " + day.info.news + "\n"
        if chat.send_absent_teachers and day.info.absent_teachers:
            message += "Abwesende Lehrer: " + day.info.absent_teachers + "\n"
        if chat.send_absent_classes and day.info.absent_classes:
            message += "Abwesende Klassen: " + day.info.absent_classes + "\n"
        return message

    def _build_day_date(self, day):
        return f'{day["day_name"]}, {day["date"]} ({day["week"]})\n'

    def _build_day_info(self, day):
        news = None
        absent_classes = None
        absent_teachers = None
        try:
            if "news" in day:
                news_hash = hashlib.sha1((day["date"] + "-" + day["news"]).encode()).hexdigest()
                if news_hash not in self.sent_news:
                    news = day["news"].replace("<br>", "\n").replace("<br/>", "\n").replace("\n\r", "\n")
                    if "\n" in news:
                        news += "\n"
                    self.sent_news.append(news_hash)
            if "absent-classes" in day:
                absent_classes_hash = hashlib.sha1((day["date"] + "-" + day["absent-classes"]).encode()).hexdigest()
                if absent_classes_hash not in self.sent_absent_classes:
                    absent_classes = day["absent-classes"]
                    self.sent_absent_classes.append(absent_classes_hash)
            if "absent-teachers" in day:
                absent_teachers_hash = hashlib.sha1(
                    (day["date"] + "-" + day["absent-teachers"]).encode()).hexdigest()
                if absent_teachers_hash not in self.sent_absent_teachers:
                    absent_teachers = day["absent-teachers"]
                    self.sent_absent_teachers.append(absent_teachers_hash)
        except Exception:
            logger.exception("Sending news failed")
        return DayInfo(news, absent_classes, absent_teachers)

    def _build_substitutions_for_group(self, substitutions, date, group_name):
        res = []
        for substitution in substitutions:
            substitution_hash = substitution.get_hash(date, group_name)
            if substitution_hash not in self.sent_substitutions:
                self.sent_substitutions.append(substitution_hash)
                res.append(substitution.get_text())
        return "\n".join(res)

    def _build_substitutions(self, substitutions, date):
        res = {}
        for group_name, group_substitutions in substitutions.items():
            text = self._build_substitutions_for_group(group_substitutions, date, group_name)
            if text:
                res[group_name] = text
        return res
