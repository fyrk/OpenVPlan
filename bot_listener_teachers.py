#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json
import os

from bot.db.teachers import TeacherDatabaseBot
from bot.listener.base import run_bot_listener
from bot.listener.teachers import TeacherBotListener
from common.db_connector import get_connection
from logging_tool import create_logger

os.chdir(os.path.abspath(os.path.dirname(__file__)))

create_logger("bot-listener-teachers")

with open("bot/secret.json") as f:
    secret = json.load(f)

connection, commands = get_connection(secret)
try:
    run_bot_listener(secret["token_teachers"], TeacherDatabaseBot, connection, commands,
                     TeacherBotListener, "teachers", "teacher_commands")
finally:
    connection.close()
