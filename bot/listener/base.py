import base64
import datetime
import logging
import re
from typing import Type

import asynctelebot
from asynctelebot.methods import SendMessage, EditMessageText
from asynctelebot.types import ForceReply, Message
from asynctelebot.utils import determine_message_content_type

from bot.db.base import DatabaseBot, DatabaseChat
from bot.listener.texts import BotTexts

logger = logging.getLogger()

MOIN = re.compile(r"\bmoin\b", re.IGNORECASE)


def str_from_timestamp(timestamp):
    return datetime.datetime.fromtimestamp(timestamp).strftime("%H:%M:%S")


class SubstitutionsBotListener:
    def __init__(self, bot: DatabaseBot, texts: BotTexts, available_settings, commands):
        self.bot = bot
        self.texts = texts
        self.available_settings = available_settings
        self.handler = asynctelebot.UpdateHandler(self.bot)
        self.handler.add_restriction_allowed_language_codes("de", help_text=self.texts["wrong-language-code"])
        self.handler.subscribe_message(commands=commands["start"])(self.start)
        self.handler.subscribe_message(commands=commands["help"])(self.help)
        self.handler.subscribe_message(commands=commands["select"])(self.do_select)
        self.handler.subscribe_message(commands=commands["settings"])(self.show_settings)
        self.handler.subscribe_message(commands=commands["reset"])(self.reset)
        self.handler.subscribe_message()(self.all_messages)
        self.handler.subscribe_callback_query()(self.all_callbacks)

    def _create_selection_info_text(self, selection):
        raise NotImplementedError

    def send_selection_set(self, chat_id, selection, was_selected_in_start_command=False):
        raise NotImplementedError

    async def start(self, message):
        logger.info(f"{message.chat.id} {str_from_timestamp(message.date)} COMMAND /start ({message.from_.first_name})")
        # noinspection PyBroadException
        try:
            text = message.text.strip()
            if len(text) % 4 != 0:
                text += (4 - len(text) % 4) * "="
            selection_string = base64.b64decode(text[7:]).decode("utf-8")
        except Exception:
            pass
        else:
            chat = self.bot.chats.get_from_msg(message)
            chat.set_selection_from_string(selection_string)
            if chat.has_selection():
                await chat.send(self.texts["help"])
                return self.send_selection_set(chat.chat_id, chat.get_pretty_selection(), True)
        return await self.help(message)

    async def help(self, message):
        logger.info(f"{message.chat.id} {str_from_timestamp(message.date)} COMMAND /help ({message.from_.first_name})")
        return SendMessage(message.chat.id, self.texts["help"])

    async def do_select(self, message):
        logger.info(f"{message.chat.id} {str_from_timestamp(message.date)} COMMAND select ({message.from_.first_name})")
        chat = self.bot.chats.get_from_msg(message)
        sent_message = (await chat.send(self.texts["send-me-selection"], reply_markup=ForceReply()))
        chat.status = "do-select:" + str(sent_message.message_id)

    def create_settings_keyboard(self, chat):
        markup = asynctelebot.types.InlineKeyboardMarkup()
        for setting, values in self.available_settings.items():
            value = str(values[0]) if chat.get(setting) == values[1] else str(values[1])
            markup.add_row(asynctelebot.types.InlineKeyboardButton(self.texts["settings"][setting][value],
                                                                   callback_data="setting-" + setting + "-" + value))
        return markup

    def create_settings_text(self, chat: DatabaseChat):
        enabled = []
        disabled = []
        for name in ("news", "absent_classes", "absent_teachers"):
            if chat.get("send_" + name):
                enabled.append(name)
            else:
                disabled.append(name)
        if chat.has_selection():
            message = self._create_selection_info_text(chat.get_parsed_selection())
        else:
            message = self.texts["settings-info-no-selection"]
        if enabled:
            if len(enabled) == 1:
                message += self.texts["settings-info-enabled"].format(self.texts[enabled[0]])
            else:
                message += self.texts["settings-info-enabled"].format(
                    ", ".join(self.texts[name] for name in enabled[:-1]) +
                    self.texts["and"] + self.texts[enabled[-1]])
        if disabled:
            if len(disabled) == 1:
                message += self.texts["settings-info-disabled"].format(self.texts[disabled[0]])
            else:
                message += self.texts["settings-info-disabled"].format(
                    ", ".join(self.texts[name] for name in disabled[:-1]) +
                    self.texts["and"] + self.texts[disabled[-1]])
        return message

    async def show_settings(self, message: Message):
        logger.info(f"{message.chat.id} {str_from_timestamp(message.date)} COMMAND /einst ({message.from_.first_name})")
        chat = self.bot.chats.get_from_msg(message)
        return SendMessage(message.chat.id, self.create_settings_text(chat),
                           parse_mode="html",
                           reply_markup=self.create_settings_keyboard(chat))

    async def reset(self, message):
        logger.info(f"{message.chat.id} {str_from_timestamp(message.date)} COMMAND /reset ({message.from_.first_name})")
        self.bot.chats.get_from_msg(message).remove_all_messages()
        self.bot.chats.reset_chat(message.chat.id)
        logger.debug("Reset successful for chat id '" + str(message.chat.id) + "'")
        return SendMessage(message.chat.id, self.texts["reset-successful"])

    async def all_messages(self, message: Message):
        logger.info(f"{message.chat.id} {str_from_timestamp(message.date)} ALL MESSAGES ({message.from_.first_name})")
        if determine_message_content_type(message) == "text":
            logger.debug("Message: " + message.text)
            chat = self.bot.chats.try_get_from_msg(message)
            if chat is not None and chat.status.startswith("do-select:") and message.reply_to_message:
                message_id = int(chat.status.split(":", 1)[1])
                if message.reply_to_message.message_id == message_id:
                    logger.debug("Chat '{}' selected '{}'".format(chat.chat_id, message.text))
                    chat.set_selection_from_string(message.text)
                    return self.send_selection_set(chat.chat_id, chat.get_pretty_selection())

            if MOIN.search(message.text):
                logger.debug("MOIN MOIN")
                return SendMessage(message.chat.id, self.texts["MOIN"])
            else:
                logger.debug("Unknown text")
                return SendMessage(message.chat.id, self.texts["unknown"])
        else:
            return SendMessage(message.chat.id, self.texts["send-only-text"])

    async def all_callbacks(self, callback: asynctelebot.types.CallbackQuery):
        logger.info(f"{callback.message.chat.id} {str_from_timestamp(callback.message.date)} CALLBACK "
                    f"({callback.message.chat.first_name})")
        chat = self.bot.chats.try_get(callback.message.chat.id)
        if chat is not None and callback.data.startswith("setting-"):
            name, value_string = callback.data[8:].split("-", 1)
            values = self.available_settings[name]
            value = values[0] if str(values[0]) == value_string else values[1]
            if value != chat.get(name):
                chat.set(name, value)
                await self.bot.answer_callback_query(callback.id,
                                                     self.texts["settings"][name]["selected-" + value_string])
                return EditMessageText(self.create_settings_text(chat), callback.message.chat.id,
                                       callback.message.message_id, parse_mode="html",
                                       reply_markup=self.create_settings_keyboard(chat))


def run_bot_listener(logger_name, token, db_bot_class: Type[DatabaseBot], db_connection,
                     bot_listener_class: Type[SubstitutionsBotListener], bot_texts_name, settings_command_key):
    import json
    from logging_tool import create_logger

    logger = create_logger(logger_name)

    with open("bot/settings.json", "r", encoding="utf-8") as f:
        settings = json.load(f)
    logger.info("Starting bot...")
    with open("bot/texts.json", "r", encoding="utf-8") as f:
        texts_all = json.load(f)
    texts = texts_all["common"]
    texts.update(texts_all[bot_texts_name])
    texts = BotTexts(texts)
    db_bot = db_bot_class(token, db_connection)
    db_bot.chats.try_create_table()
    bot_listener = bot_listener_class(db_bot, texts, settings["available_settings"], settings[settings_command_key])
    try:
        logger.info("Polling")
        bot_listener.handler.polling(infinite=True, error_wait=10)
    finally:
        db_connection.close()
        logger.error("Error occurred, saving and closing")
