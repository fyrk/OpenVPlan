import json

from asynctelebot import types as t

# from asynctelebot.bot import Bot

print(t.Location.__required__)

with open("secret.json", "r") as f:
    bot = Bot(json.load(f)["token"])

bot.polling()
