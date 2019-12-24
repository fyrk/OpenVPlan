import asyncio
import json

import asynctelebot

with open("secret.json", "r") as f:
    secret = json.load(f)
    bot_students = asynctelebot.Bot(secret["token_students"])
    bot_teachers = asynctelebot.Bot(secret["token_teachers"])


async def delete_webhooks():
    await asyncio.gather(
        await bot_students.delete_webhook(),
        await bot_teachers.delete_webhook()
    )

asyncio.run(delete_webhooks())
