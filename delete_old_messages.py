import datetime
import json

from bot_utils import CustomAsyncTeleBot


def create_date_timestamp(date):
    return int(datetime.datetime.strptime(date, "%d.%m.%Y").timestamp())


with open("data/secret.json", "r") as f:
    bot = CustomAsyncTeleBot(json.load(f)["token"], "data/chats.json")

bot.chats.delete_old_messages(create_date_timestamp(datetime.datetime.now()))
