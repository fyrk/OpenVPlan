import asyncio
import json
import sqlite3
from functools import partial

import asynctelebot

logger = None


def get_texts():
    with open("data/static/texts.json", "r") as f:
        return {key: ("\n".join(value) if type(value) == list else value) for key, value in json.load(f).items()}


def adapter_list(lst):
    return ",".join(str(e) for e in lst)


def converter_list_int(data):
    return [int(e) for e in data.split(b",")]


def converter_list_text(data):
    return [str(e, "utf-8", "ignore") for e in data.split(b",")]


def adapter_json(obj):
    return json.dumps(obj)


def converter_json(data):
    return json.loads(data, encoding="utf-8")


sqlite3.register_adapter(list, adapter_list)
sqlite3.register_converter("LIST_INT", converter_list_int)
sqlite3.register_converter("LIST_TEXT", converter_list_text)
sqlite3.register_adapter(dict, adapter_json)
sqlite3.register_converter("JSON", converter_json)


class CustomBot(asynctelebot.Bot):
    chats: "ChatList"

    def __init__(self, api_token, chats_filename):
        self.chats = ChatList(chats_filename, self)
        asynctelebot.Bot.__init__(self, api_token)


class ChatList:
    def __init__(self, filename, bot: CustomBot):
        self._filename = filename
        self._bot = bot

    def open(self):
        self._conn = sqlite3.connect(self._filename, detect_types=sqlite3.PARSE_DECLTYPES)
        self._conn.row_factory = partial(Chat.from_row, bot=self._bot)
        self._cursor = self._conn.cursor()

    def save(self):
        self._conn.commit()

    def close(self):
        self._conn.close()

    def get(self, chat_id: int) -> "Chat":
        logger.debug("Get chat '" + str(chat_id) + "'")
        self._cursor.execute("""SELECT * FROM chats WHERE chat_id=?""", (chat_id,))
        chat = self._cursor.fetchone()
        if chat is None:
            logger.debug("Unknown chat, creating new")
            self._cursor.execute("""INSERT INTO chats VALUES (?,?,?,?,?,?,?,?)""", (chat_id, "", [], "text", 1, 1, 1,
                                                                                    {}))
            self._conn.commit()
            return Chat(self._bot, self._cursor, chat_id)
        return chat

    def get_from_msg(self, message) -> "Chat":
        return self.get(message.chat.id)

    def all_chats(self):
        self._cursor.execute("""SELECT * FROM chats""")
        return self._cursor.fetchall()

    def reset_chat(self, chat_id: int):
        self._cursor.execute("""DELETE FROM chats WHERE chat_id=?""", (chat_id,))
        self._conn.commit()

    def remove_old_messages(self, min_time):
        tasks = []
        self.open()
        for chat in self.all_chats():
            tasks.extend(chat.remove_old_messages(min_time))
        self.save()
        self.close()
        if tasks:
            print(asyncio.get_event_loop().run_until_complete(asyncio.wait(tasks)))


class Chat:
    _cursor: sqlite3.Cursor

    def __init__(self, bot: CustomBot, cursor: sqlite3.Cursor, chat_id: int, status="",
                 selected_classes=None, send_format="text", send_news=True, send_absent_classes=True,
                 send_absent_teachers=True, sent_messages=None):
        self._bot = bot
        self._cursor = cursor
        self._chat_id = chat_id
        self._status = status
        if selected_classes is None:
            self._selected_classes = []
        else:
            self._selected_classes = selected_classes
        self._send_format = send_format
        self._send_news = send_news
        self._send_absent_classes = send_absent_classes
        self._send_absent_teachers = send_absent_teachers
        if sent_messages is None:
            self._sent_messages = {}
        else:
            self._sent_messages = sent_messages

    def __repr__(self):
        return """Chat(bot={}, 
    cursor={}, 
    chat_id={}, 
    status={},
    selected_classes={}, 
    send_format={}, 
    send_news={}, 
    send_absent_classes={},
    send_absent_teachers={}, 
    sent_messages={}
)""".format(repr(self._bot), repr(self._cursor), repr(self._chat_id), repr(self._status), repr(self._selected_classes),
            repr(self._send_format), repr(self._send_news), repr(self._send_absent_classes),
            repr(self._send_absent_teachers), repr(self._sent_messages))

    @staticmethod
    def from_row(cursor, row, bot):
        return Chat(bot, cursor, *row)

    def reset_status(self):
        self._cursor.execute("""UPDATE chats SET status='' WHERE chat_id=?""", (self._chat_id,))

    async def send(self, text, reply_markup=None, parse_mode=None):
        res = await self._bot.send_message(self.chat_id, text, reply_markup=reply_markup, parse_mode=parse_mode)
        return res

    async def send_substitution(self, day_timestamp, text, reply_markup=None, parse_mode=None):
        day_timestamp = str(day_timestamp)
        message = await self.send(text, reply_markup, parse_mode)
        try:
            self._sent_messages[day_timestamp].append(message.message_id)
        except KeyError:
            self._sent_messages[day_timestamp] = [message.message_id]
        logger.debug("Sent Substitution to {}: {}".format(self.chat_id, message.message_id))
        try:
            self._cursor.execute("UPDATE chats SET sent_messages=? WHERE chat_id=?", (self._sent_messages, self._chat_id))
        except Exception:
            logger.error("MESSAGE NOT ADDED TO SENT_MESSAGES: {} ({})".format(message.message_id, self.chat_id))

    def remove_old_messages(self, min_time):
        new_sent_messages = self._sent_messages.copy()
        for day, messages in self._sent_messages.items():
            if int(day) <= min_time:
                for message_id in messages:
                    yield asyncio.ensure_future(self._bot.edit_message_text(
                        "Alte Nachrichten zum Vertretungsplan werden gelöscht. ", self.chat_id, message_id))
                    logger.info("Deleted {} from {}".format(message_id, self.chat_id))
                del new_sent_messages[day]
        self.sent_messages = new_sent_messages
        self._cursor.execute("UPDATE chats SET sent_messages=? WHERE chat_id=?", (self._sent_messages, self._chat_id))

    def get(self, property_name):
        return self.__dict__["_" + property_name]

    def set(self, property_name, value):
        self.__dict__["_" + property_name] = value
        assert " " not in property_name
        self._cursor.execute("UPDATE chats SET {}=? WHERE chat_id=?".format(property_name), (value, self._chat_id))

    @property
    def chat_id(self):
        return self._chat_id

    @property
    def status(self):
        return self._status

    @status.setter
    def status(self, value):
        self.set("status", value)

    @property
    def selected_classes(self):
        return self._selected_classes

    @selected_classes.setter
    def selected_classes(self, value):
        self.set("selected_classes", value)

    @property
    def send_format(self):
        return self._send_format

    @send_format.setter
    def send_format(self, value):
        self.set("send_format", value)

    @property
    def send_news(self):
        return self._send_news

    @send_news.setter
    def send_news(self, value):
        self.set("sent_news", value)

    @property
    def send_absent_classes(self):
        return self._send_absent_classes

    @send_absent_classes.setter
    def send_absent_classes(self, value):
        self.set("send_absent_classes", value)

    @property
    def send_absent_teachers(self):
        return self._send_absent_teachers

    @send_absent_teachers.setter
    def send_absent_teachers(self, value):
        self.set("send_absent_teachers", value)

    @property
    def sent_messages(self):
        return self._sent_messages

    @sent_messages.setter
    def sent_messages(self, value):
        self.set("sent_messages", value)
