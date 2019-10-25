import datetime
import json

import bot_utils
from logging_tool import create_logger

logger = create_logger("delete-old-msg")

bot_utils.logger = logger


def create_date_timestamp(date):
    return int(datetime.datetime.strptime(date, "%d.%m.%Y").timestamp())


with open("secret.json", "r") as f:
    bot = bot_utils.CustomBot(json.load(f)["token"], "data/chats.sqlite3")

bot.chats.remove_old_messages(create_date_timestamp(datetime.datetime.strftime(datetime.datetime.now(), "%d.%m.%Y")))
