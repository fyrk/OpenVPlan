#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import os

from bot.db.connector import get_connection
from bot.db.students import StudentDatabaseBot
from bot.db.teachers import TeacherDatabaseBot
from bot.listener.students import StudentBotListener
from bot.listener.teachers import TeacherBotListener
from bot.listener.texts import BotTexts
from logging_tool import create_logger

os.chdir(os.path.abspath(os.path.dirname(__file__)))

logger = create_logger("bot-listener-webhook")

with open("bot/secret.json") as f:
    secret = json.load(f)

with open("bot/settings.json", "r", encoding="utf-8") as f:
    settings = json.load(f)
logger.info("Starting bot...")
with open("bot/texts.json", "r", encoding="utf-8") as f:
    texts = json.load(f)

texts_students = BotTexts(texts, "students")
texts_teachers = BotTexts(texts, "teachers")


db_bot_students = StudentDatabaseBot(secret["token_students"], None)
db_bot_teachers = TeacherDatabaseBot(secret["token_teachers"], None)
bot_listener_students = StudentBotListener(db_bot_students, texts_students, settings["available_settings"],
                                           settings["student_commands"])
bot_listener_teachers = TeacherBotListener(db_bot_teachers, texts_teachers, settings["available_settings"],
                                           settings["teacher_commands"])


def application(environ, start_response):
    try:
        connection = get_connection(secret)
        if environ["PATH_INFO"] == "/students":
            logger.info("Update for STUDENTS")
            db_bot_students.chats.connection = connection
            result = bot_listener_students.handler.wsgi_application(environ, start_response)
            connection.close()
            return result
        elif environ["PATH_INFO"] == "/teachers":
            logger.info("Update for TEACHERS")
            db_bot_teachers.chats.connection = connection
            result = bot_listener_teachers.handler.wsgi_application(environ, start_response)
            connection.close()
            return result
    except Exception:
        logger.exception("Exception while processing bot update")
        start_response("500 Internal Server Error", [("Content-Type", "text/text")])
        return ["Error while processing bot update".encode("utf-8")]

    start_response("303 See Other", [("Location", "https://gawvertretung.florian-raediker.de")])
    return []
