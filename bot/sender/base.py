import asyncio
import datetime
import hashlib
import json
import logging
from collections import deque
from typing import List, NamedTuple, Tuple

from bot.db.base import DatabaseChat, DatabaseBot
from common.base import SubstitutionDay, BaseSubstitutionGroup
from common.utils import create_date_timestamp


class Day(NamedTuple):
    timestamp: int
    date_info: str
    info: "DayInfo"
    substitutions: List[Tuple[str, str]]


class DayInfo(NamedTuple):
    news: str
    absent_classes: str
    absent_teachers: str


class BaseMessageSender:
    def __init__(self, bot: DatabaseBot, sent_messages_file: str):
        self.logger = logging.getLogger()
        self.bot = bot
        self.sent_messages_file = sent_messages_file
        try:
            with open(sent_messages_file, "r") as f:
                sent_messages = json.load(f)
        except FileNotFoundError:
            self.sent_substitutions = deque([], maxlen=200)
            self.sent_news = deque([], maxlen=20)
            self.sent_absent_classes = deque([], maxlen=20)
            self.sent_absent_teachers = deque([], maxlen=20)
        else:
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

    async def send_messages(self, days: List[SubstitutionDay]):
        self.logger.info(f"Send messages {days}")
        current_timestamp = create_date_timestamp(datetime.datetime.now())
        for day in (
                Day(day.timestamp,
                    self._build_day_date(day),
                    self._build_day_info(day),
                    self._build_substitutions(day.substitution_groups, day.date))
                for day in days if day.timestamp >= current_timestamp):
            self.logger.debug(f"Sending day: {day}")

            await asyncio.gather(*(await self._send_message_to(chat, day)
                                   for chat in self.bot.chats.all_chats()))

    async def _send_message_to(self, chat: DatabaseChat, day: Day):
        raise NotImplementedError

    def _build_message_info_text(self, chat: DatabaseChat, day: Day):
        message = ""
        if chat.send_news and day.info.news:
            message += "Nachrichten: " + day.info.news + "\n"
        if chat.send_absent_teachers and day.info.absent_teachers:
            message += "Abwesende Lehrer: " + day.info.absent_teachers + "\n"
        if chat.send_absent_classes and day.info.absent_classes:
            message += "Abwesende Klassen: " + day.info.absent_classes + "\n"
        return message

    def _build_day_date(self, day: SubstitutionDay):
        return f"{day.day_name}, {day.date} ({day.week})\n"

    def _build_day_info(self, day: SubstitutionDay):
        news = None
        absent_classes = None
        absent_teachers = None
        try:
            if day.news:
                news_hash = hashlib.sha1((day.date + "-" + day.news).encode()).hexdigest()
                if news_hash not in self.sent_news:
                    news = day.news.replace("<br>", "\n").replace("<br/>", "\n").replace("\n\r", "\n")
                    if "\n" in news:
                        news += "\n"
                    self.sent_news.append(news_hash)
            if day.absent_classes:
                absent_classes_hash = hashlib.sha1((day.date + "-" + day.absent_classes).encode()).hexdigest()
                if absent_classes_hash not in self.sent_absent_classes:
                    absent_classes = day.absent_classes
                    self.sent_absent_classes.append(absent_classes_hash)
            if day.absent_teachers:
                absent_teachers_hash = hashlib.sha1(
                    (day.date + "-" + day.absent_teachers).encode()).hexdigest()
                if absent_teachers_hash not in self.sent_absent_teachers:
                    absent_teachers = day.absent_teachers
                    self.sent_absent_teachers.append(absent_teachers_hash)
        except Exception:
            self.logger.exception("Sending news failed")
        return DayInfo(news, absent_classes, absent_teachers)

    def _build_substitutions_for_group(self, substitution_group: BaseSubstitutionGroup, date):
        res = []
        for substitution in substitution_group.substitutions:
            substitution_hash = substitution.get_hash(date, substitution_group.group_name)
            if substitution_hash not in self.sent_substitutions:
                self.sent_substitutions.append(substitution_hash)
                res.append(substitution.get_text())
        return "\n".join(res)

    def _build_substitutions(self, substitution_groups: List[BaseSubstitutionGroup], date):
        res = []
        for substitution_group in substitution_groups:
            text = self._build_substitutions_for_group(substitution_group, date)
            if text:
                res.append((substitution_group.group_name, text))
        return res
