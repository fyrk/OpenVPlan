#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import os

from bot.db.connector import get_connection
from bot.db.students import StudentDatabaseBot
from bot.listener.base import run_bot_listener
from bot.listener.students import StudentBotListener
from logging_tool import create_logger

os.chdir(os.path.abspath(os.path.dirname(__file__)))

create_logger("bot-listener-students")

with open("bot/secret.json") as f:
    secret = json.load(f)

connection = get_connection(secret)
try:
    run_bot_listener(secret["token_students"], StudentDatabaseBot, connection, StudentBotListener, "students",
                     "student_commands")
finally:
    connection.close()
