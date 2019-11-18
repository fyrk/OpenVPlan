#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os

from bot.listener.base import run_bot_listener
from bot.listener.students import StudentBotListener

os.chdir(os.path.dirname(__file__))

run_bot_listener("bot-listener-students", StudentBotListener, "students", "student_commands")
