import asyncio
import datetime
import json
import os

from bot.db.students import StudentDatabaseBot
from bot.db.teachers import TeacherDatabaseBot
from common.db_connector import get_connection
from common.utils import create_date_timestamp
from logging_tool import create_logger

os.chdir(os.path.abspath(os.path.dirname(__file__)))


logger = create_logger("delete-old-msg")


with open("bot/secret.json", "r") as f:
    secret = json.load(f)
    connection = get_connection(secret)
    bot_students = StudentDatabaseBot(secret["token_students"], connection)
    bot_teachers = TeacherDatabaseBot(secret["token_teachers"], connection)

min_time = create_date_timestamp(datetime.datetime.now())

logger.info(f"Minimum time is {min_time}")


async def delete_old_messages():
    await asyncio.gather(
        bot_students.chats.remove_old_messages(min_time),
        bot_teachers.chats.remove_old_messages(min_time)
    )


asyncio.run(delete_old_messages())
connection.close()
