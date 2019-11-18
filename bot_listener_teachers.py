#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os

from bot.listener.base import run_bot_listener
from bot.listener.teachers import TeacherBotListener

os.chdir(os.path.dirname(__file__))

run_bot_listener("bot-listener-teachers", TeacherBotListener, "teachers", "teacher_commands")
