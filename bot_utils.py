import json
import time
from typing import Union, Dict

from telebot import TeleBot, AsyncTeleBot


class CustomAsyncTeleBot(AsyncTeleBot):
    chats: "ChatList"

    def __init__(self, token, chat_filename, threaded=True, skip_pending=False, num_threads=2):
        self.chats = ChatList(chat_filename, self)
        TeleBot.__init__(self, token, threaded, skip_pending, num_threads)


class ChatList:
    _data: Dict[str, "Chat"]

    def __init__(self, file, bot: CustomAsyncTeleBot):
        self._file = file
        self._bot = bot
        self.reload()

    def __iter__(self):
        return iter(self._data.values())

    def save(self):
        exception = None
        for _ in range(3):
            try:
                f = open(self._file, "w")
            except OSError as e:
                time.sleep(0.3)
            else:
                break
        else:
            raise OSError("Could not write file '" + self._file + "': " + str(exception))
        print("write data", self._data)
        json.dump(self._data, f)
        f.close()

    def reload(self):
        exception = None
        for _ in range(3):
            try:
                f = open(self._file, "r")
            except OSError as e:
                time.sleep(0.3)
                exception = e
            else:
                break
        else:
            raise OSError("Could not read file '" + self._file + "': " + str(exception))
        self._data = json.load(f)
        f.close()
        for chat_id, chat_data in self._data.items():
            self._data[chat_id] = Chat(chat_id, self._bot, chat_data)

    def get(self, chat_id: Union[int, str]) -> "Chat":
        chat_id = str(chat_id)
        try:
            return self._data[chat_id]
        except KeyError:
            self._data[chat_id] = Chat(chat_id, self._bot)
            return self._data[chat_id]

    def get_from_msg(self, message):
        return self.get(message.chat.id)

    def reset_chat(self, chat_id):
        chat_id = str(chat_id)
        del self._data[chat_id]

    def delete_old_messages(self, min_time):
        for chat in self._data.values():
            chat.delete_old_messages(min_time)
        self.save()


class Chat(dict):
    def __init__(self, chat_id: Union[int, str], bot: CustomAsyncTeleBot, dictionary=None):
        self._chat_id = chat_id
        self._bot = bot
        super().__init__(dictionary)
        if "sent-messages" not in self:
            self["sent-messages"] = {}

    def reset_status(self):
        self.status = ""

    def send(self, text, reply_markup=None, parse_mode=None):
        return self._bot.send_message(self.chat_id, text, reply_markup=reply_markup, parse_mode=parse_mode)

    def send_substitution(self, day_timestamp, text, reply_markup=None, parse_mode=None):
        day_timestamp = str(day_timestamp)
        message = self.send(text, reply_markup, parse_mode).wait()
        try:
            self["sent-messages"][day_timestamp].append(message.message_id)
        except KeyError:
            self["sent-messages"][day_timestamp] = [message.message_id]

    def delete_old_messages(self, min_time):
        for day, messages in self["sent-messages"].items():
            if int(day) < min_time:
                for message_id in messages:
                    self._bot.delete_message(self.chat_id, message_id)
        self["sent-messages"] = {}

    def set(self, key, value):
        self[key] = value

    @property
    def chat_id(self):
        return int(self._chat_id)

    @property
    def status(self):
        return self.get("status", "")

    @status.setter
    def status(self, value):
        self["status"] = value

    @property
    def selected_classes(self):
        return self.get("selected-classes", None)

    @selected_classes.setter
    def selected_classes(self, value):
        self["selected-classes"] = value

    @property
    def send_format(self):
        return self.get("send-format", "text")

    @send_format.setter
    def send_format(self, value):
        self["send-format"] = value

    @property
    def send_news(self):
        return self.get("send-news", True)

    @send_news.setter
    def send_news(self, value):
        self["send-news"] = value

    @property
    def send_absent_classes(self):
        return self.get("send-absent-classes", True)

    @send_absent_classes.setter
    def send_absent_classes(self, value):
        self["send-absent-classes"] = value

    @property
    def send_absent_teachers(self):
        return self.get("send-absent-teachers", True)

    @send_absent_teachers.setter
    def send_absent_teachers(self, value):
        self["send-absent-teachers"] = value
