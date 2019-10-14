import json
import sqlite3
from functools import partial

from telebot import TeleBot, AsyncTeleBot


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


class CustomAsyncTeleBot(AsyncTeleBot):
    chats: "ChatList"

    def __init__(self, token, chat_filename, threaded=True, skip_pending=False, num_threads=2):
        self.chats = ChatList(chat_filename, self)
        TeleBot.__init__(self, token, threaded, skip_pending, num_threads)


class ChatList:
    def __init__(self, filename, bot: CustomAsyncTeleBot):
        self._conn = sqlite3.connect(filename, detect_types=sqlite3.PARSE_DECLTYPES)
        self._conn.row_factory = partial(Chat.from_row, bot=bot)
        self._cursor = self._conn.cursor()
        self._bot = bot

    def __iter__(self):
        self._cursor.execute("""SELECT * FROM chats""")
        return iter(self._cursor)

    def save(self):
        self._conn.commit()

    def close(self):
        self._conn.close()

    def get(self, chat_id: int) -> "Chat":
        print("get chat with id", chat_id)
        self._cursor.execute("""SELECT * FROM chats WHERE chat_id=?""", (chat_id,))
        chat = self._cursor.fetchone()
        print("got", chat)
        if chat is None:
            print("chat is None...")
            self._cursor.execute("""INSERT INTO chats VALUES (?,?,?,?,?,?,?,?)""", (chat_id, "", [], "text", 1, 1, 1,
                                                                                    {}))
            self._conn.commit()
            return Chat(self._bot, self._cursor, chat_id)
        return chat

    def get_from_msg(self, message):
        return self.get(message.chat.id)

    def reset_chat(self, chat_id: int):
        self._cursor.execute("""DELETE FROM chats WHERE chat_id=?""", (chat_id,))
        self._conn.commit()

    def delete_old_messages(self, min_time):
        for chat in self:
            chat.delete_old_messages(min_time)
        self.save()


class Chat:
    _cursor: sqlite3.Cursor

    def __init__(self, bot: CustomAsyncTeleBot, cursor: sqlite3.Cursor, chat_id: int, status="",
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
        print("converting row to Chat", row)
        return Chat(bot, cursor, *row)

    def reset_status(self):
        self._cursor.execute("""UPDATE chats SET status='' WHERE chat_id=?""", (self._chat_id,))

    def send(self, text, reply_markup=None, parse_mode=None):
        return self._bot.send_message(self.chat_id, text, reply_markup=reply_markup, parse_mode=parse_mode)

    def send_substitution(self, day_timestamp, text, reply_markup=None, parse_mode=None):
        day_timestamp = str(day_timestamp)
        message = self.send(text, reply_markup, parse_mode).wait()
        try:
            self._sent_messages[day_timestamp].append(message.message_id)
        except KeyError:
            self._sent_messages[day_timestamp] = [message.message_id]
        self._cursor.execute("UPDATE chats SET sent_messages=? WHERE chat_id=?", (self._sent_messages, self._chat_id))

    def delete_old_messages(self, min_time):
        for day, messages in self._sent_messages.items():
            if int(day) < min_time:
                for message_id in messages:
                    self._bot.delete_message(self.chat_id, message_id)
        self.sent_messages = {}

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
