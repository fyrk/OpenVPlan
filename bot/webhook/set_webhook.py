import asyncio
import json

import asynctelebot

with open("secret.json", "r") as f:
    secret = json.load(f)
    bot_students = asynctelebot.Bot(secret["token_students"])
    bot_teachers = asynctelebot.Bot(secret["token_teachers"])


async def set_webhooks():
    await asyncio.gather(
        await bot_students.set_webhook(
            "https://gawvertretung.florian-raediker.de/bot/Mcx5QOA91UjR2O2Chi01fGZI0b6j8GdAOM/students",
            allowed_updates=["message", "callback_query"]
        ),
        await bot_teachers.set_webhook(
            "https://gawvertretung.florian-raediker.de/bot/Mcx5QOA91UjR2O2Chi01fGZI0b6j8GdAOM/teachers",
            allowed_updates=["message", "callback_query"]
        )
    )

asyncio.run(set_webhooks())
