import asyncio
import json
import os
import pickle
import time
from functools import partial

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

from bot.db.connector import get_connection
from bot.db.students import StudentDatabaseBot
from bot.db.teachers import TeacherDatabaseBot
from bot.sender.students import StudentMessageSender
from bot.sender.teachers import TeacherMessageSender
from logging_tool import create_logger

os.chdir(os.path.abspath(os.path.dirname(__file__)))


class BotSender(FileSystemEventHandler):
    def __init__(self, bot_token_students, bot_token_teachers, create_connection_callback, loop):
        self.__bot_token_students = bot_token_students
        self.__bot_token_teachers = bot_token_teachers
        self.connection_students = None
        self.connection_teachers = None
        self.bot_students = None
        self.bot_teachers = None
        self.sender_students = None
        self.sender_teachers = None
        self.create_connection = create_connection_callback
        self.loop = loop
        self.connection = None
        self.last_status = None

    def _create_bots_if_necessary(self):
        # if self.connection is None:
        if self.connection:
            self.connection.close()
        self.connection = self.create_connection()
        self.bot_students = StudentDatabaseBot(self.__bot_token_students, self.connection)
        self.bot_teachers = TeacherDatabaseBot(self.__bot_token_teachers, self.connection)
        self.sender_students = StudentMessageSender(self.bot_students, "data/sent_messages_students.json")
        self.sender_teachers = TeacherMessageSender(self.bot_teachers, "data/sent_messages_teachers.json")

    def on_modified(self, event):
        try:
            if event.src_path == "data/substitutions/substitutions.pickle":
                logger.info("SUBSTITUTIONS CHANGED")
                self.on_substitutions_modified()
        except Exception:
            logger.exception("Exception occurred while processing file update")

    def on_substitutions_modified(self, *_):
        logger.info("on_substitutions_modified")
        try:
            with open("data/substitutions/substitutions.pickle", "rb") as f:
                status, data_students, data_teachers = pickle.load(f)
        except EOFError:
            logger.exception("Could not read substitutions.pickle, writing not finished yet")
            time.sleep(0.5)
            self.on_substitutions_modified()
        else:
            logger.debug(f"New status is {repr(status)}, old is {repr(self.last_status)}")
            if status != self.last_status:
                self._create_bots_if_necessary()
                self.last_status = status
                asyncio.set_event_loop(self.loop)
                self.loop.run_until_complete(asyncio.gather(
                    self.sender_students.send_messages(data_students),
                    self.sender_teachers.send_messages(data_teachers)
                ))
                self.save()

    def save(self):
        if self.connection:
            self.sender_students.save_sent_messages()
            self.sender_teachers.save_sent_messages()


if __name__ == "__main__":
    logger = create_logger("bot-sender")
    logger.info("Starting bot sender...")
    try:

        with open("bot/secret.json", "r") as f:
            secret = json.load(f)

        sender = BotSender(secret["token_students"], secret["token_teachers"], partial(get_connection, secret=secret),
                           asyncio.new_event_loop())
        observer = Observer()
        observer.schedule(sender, "data/substitutions")
        logger.info("Bot sender started")
        observer.start()
        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            observer.stop()
        observer.join()
    except Exception:
        logger.exception("Exception occured")
else:
    import logging

    logger = logging.getLogger()
