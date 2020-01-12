import asyncio
import json

import asynctelebot

with open("secret.json", "r") as f:
    secret = json.load(f)
    bot_students = asynctelebot.Bot(secret["token_students"])
    bot_teachers = asynctelebot.Bot(secret["token_teachers"])


async def delete_webhooks():
    await asyncio.gather(
        bot_students.delete_webhook(),
        bot_teachers.delete_webhook()
    )


asyncio.new_event_loop().run_until_complete(delete_webhooks())
bot_students.close()
bot_teachers.close()
