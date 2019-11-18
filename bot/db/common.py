import asyncio
import json
import logging

import asynctelebot

logger = logging.getLogger()


class DatabaseBot(asynctelebot.Bot):
    chats: "DatabaseChatList"

    def __init__(self, api_token, chat_list):
        self.chats = chat_list
        asynctelebot.Bot.__init__(self, api_token)


class DatabaseChatList:
    def __init__(self, bot: DatabaseBot, selection_handler):
        self._bot = bot
        self.selection_handler = selection_handler

    def open(self):
        raise NotImplementedError

    def save(self):
        raise NotImplementedError

    def close(self):
        raise NotImplementedError

    def create_new_database(self):
        raise NotImplementedError

    def get(self, chat_id: int) -> "DatabaseChat":
        raise NotImplementedError

    def get_from_msg(self, message) -> "DatabaseChat":
        return self.get(message.chat.id)

    def all_chats(self):
        raise NotImplementedError

    def reset_chat(self, chat_id: int):
        raise NotImplementedError

    def remove_old_messages(self, min_time):
        tasks = []
        self.open()
        for chat in self.all_chats():
            tasks.extend(chat.remove_old_messages(min_time))
        self.save()
        self.close()
        if tasks:
            print(asyncio.get_event_loop().run_until_complete(asyncio.wait(tasks)))


class DatabaseChat:
    def __init__(self, bot: DatabaseBot,
                 chat_id: int, status="", selection=None, send_format="text", send_news=True,
                 send_absent_classes=True, send_absent_teachers=True, sent_messages=None):
        self._bot = bot
        self._chat_id = chat_id
        self._status = status
        if selection is None:
            self._selection = []
        else:
            self._selection = self._bot.selection_handler.parse_db(selection)
        self._send_format = send_format
        self._send_news = send_news
        self._send_absent_classes = send_absent_classes
        self._send_absent_teachers = send_absent_teachers
        if sent_messages is None:
            self._sent_messages = {}
        else:
            self._sent_messages = json.loads(sent_messages)

    def __repr__(self):
        return """Chat(bot={}, 
    chat_id={}, 
    status={},
    selected_classes={}, 
    send_format={}, 
    send_news={}, 
    send_absent_classes={},
    send_absent_teachers={}, 
    sent_messages={}
)""".format(repr(self._bot), repr(self._chat_id), repr(self._status), repr(self._selected_classes),
            repr(self._send_format), repr(self._send_news), repr(self._send_absent_classes),
            repr(self._send_absent_teachers), repr(self._sent_messages))

    @staticmethod
    def from_row(cursor, row, bot):
        raise NotImplementedError

    def reset_status(self):
        raise NotImplementedError

    async def send(self, text, reply_markup=None, parse_mode=None):
        raise NotImplementedError

    async def send_substitution(self, day_timestamp, text, reply_markup=None, parse_mode=None):
        raise NotImplementedError

    def remove_all_messages(self):
        for day, messages in self._sent_messages.items():
            for message_id in messages:
                yield self._bot.edit_message_text("Alte Nachrichten zum Vertretungsplan werden gelöscht. ",
                                                  self.chat_id, message_id)

    def remove_old_messages(self, min_time):
        raise NotImplementedError

    def get(self, property_name):
        return self.__dict__["_" + property_name]

    def set(self, property_name, value):
        raise NotImplementedError

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
    def selection(self):
        return self._selected_classes

    @selection.setter
    def selection(self, value):
        self.set("selection", value)

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
