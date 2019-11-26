#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import os

from bot.db.students import StudentDatabaseBot
from bot.listener.base import run_bot_listener
from bot.listener.students import StudentBotListener
from common.db_connector import get_connection

os.chdir(os.path.dirname(__file__))

with open("bot/secret.json") as f:
    secret = json.load(f)

connection = get_connection(secret)
try:
    run_bot_listener("bot-listener-students", secret["token_students"], StudentDatabaseBot, connection,
                     StudentBotListener, "students",
                     "student_commands")
finally:
    connection.close()
