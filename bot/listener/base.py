import base64
import datetime
import logging
import re

import asynctelebot
from asynctelebot.utils import determine_message_content_type

from bot.db.sqlite import SqliteBot as DBBot
from bot.utils import BotTexts

logger = logging.getLogger()

MOIN = re.compile(r"\bmoin\b", re.IGNORECASE)


def str_from_timestamp(timestamp):
    return datetime.datetime.fromtimestamp(timestamp).strftime("%H:%M:%S")


class SubstitutionsBotListener(DBBot):
    def __init__(self, texts: BotTexts, available_settings, commands, token, filename, selection_handler):
        super().__init__(token, filename)
        self.selection_handler = selection_handler
        self.texts = texts
        self.available_settings = available_settings
        self.handler = asynctelebot.UpdateHandler(self)
        self.handler.add_restriction_allowed_language_codes("de", help_text=self.texts["wrong-language-code"])
        self.handler.subscribe_message(commands=commands["start"])(self.start)
        self.handler.subscribe_message(commands=commands["help"])(self.help)
        self.handler.subscribe_message(commands=commands["select"])(self.select_classes)
        self.handler.subscribe_message(commands=commands["settings"])(self.show_settings)
        self.handler.subscribe_message(commands=commands["reset"])(self.reset)
        self.handler.subscribe_message()(self.all_messages)
        self.handler.subscribe_callback_query(custom_filter=lambda c: True)(self.all_callbacks)

    async def start(self, message):
        logger.info(f"{message.chat.id} {str_from_timestamp(message.date)} COMMAND /start ({message.from_.first_name})")
        await self.help(message)
        try:
            text = message.text.strip()
            if len(text) % 4 != 0:
                text += (4 - len(text) % 4) * "="
            selection_string = base64.b64decode(text[7:]).decode("utf-8")
            selected_classes = self.selection_handler.parse(selection_string)
            if selected_classes:
                self.chats.open()
                chat = self.chats.get_from_msg(message)
                chat.selection = selected_classes
                self.chats.save()
                self.chats.close()
                await self.send_selection_set(chat, selected_classes, True)
        except Exception:
            pass

    async def send_selection_set(self, chat, selection, was_selected_in_start_command=False):
        raise NotImplementedError

    async def help(self, message):
        logger.info(f"{message.chat.id} {str_from_timestamp(message.date)} COMMAND /help ({message.from_.first_name})")
        self.chats.open()
        chat = self.chats.get_from_msg(message)
        chat.reset_status()
        self.chats.save()
        self.chats.close()
        await chat.send(self.texts["help"])

    async def select_classes(self, message):
        logger.info(f"{message.chat.id} {str_from_timestamp(message.date)} COMMAND /klassen "
                    f"({message.from_.first_name})")
        self.chats.open()
        chat = self.chats.get_from_msg(message)
        chat.status = "select-classes"
        self.chats.save()
        self.chats.close()
        await chat.send(self.texts["send-classes-for-selection"])

    def create_settings_keyboard(self, chat):
        markup = asynctelebot.types.InlineKeyboardMarkup()
        for setting, values in self.available_settings.items():
            print(setting, values)
            value = str(values[0]) if chat.get(setting) == values[1] else str(values[1])
            markup.add_row(asynctelebot.types.InlineKeyboardButton(self.texts["settings"][setting][value],
                                                                   callback_data="setting-" + setting + "-" + value))
        return markup

    def create_settings_text(self, chat):
        enabled = []
        disabled = []
        for name in ("news", "absent_classes", "absent_teachers"):
            if chat.get("send_" + name):
                enabled.append(name)
            else:
                disabled.append(name)
        if chat.selection:
            message = self.texts["settings-info-selected-class"
                                 if len(chat.selection) == 1 else
                                 "settings-info-selected-classes"].format(", ".join(chat.selection))
        else:
            message = self.texts["settings-info-no-classes-selected"]
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
        message += self.texts["setting-info-format"].format(self.texts[chat.get("send_format")])
        return message

    async def show_settings(self, message: asynctelebot.Message):
        logger.info(f"{message.chat.id} {str_from_timestamp(message.date)} COMMAND /einst ({message.from_.first_name})")
        self.chats.open()
        chat = self.chats.get_from_msg(message)
        chat.reset_status()
        self.chats.save()
        self.chats.close()
        await chat.send(self.create_settings_text(chat),
                        parse_mode="html",
                        reply_markup=self.create_settings_keyboard(chat))

    async def reset(self, message):
        logger.info(f"{message.chat.id} {str_from_timestamp(message.date)} COMMAND /reset ({message.from_.first_name})")
        self.chats.open()
        self.chats.get(message.chat.id).remove_all_messages()
        self.chats.reset_chat(message.chat.id)
        self.chats.save()
        self.chats.close()
        logger.debug("Reset successful for chat id '" + str(message.chat.id) + "'")
        await self.send_message(message.chat.id, self.texts["reset-successful"])

    async def all_messages(self, message: asynctelebot.Message):
        logger.info(f"{message.chat.id} {str_from_timestamp(message.date)} ALL MESSAGES ({message.from_.first_name})")
        if determine_message_content_type(message) == "text":
            logger.debug("Message: " + message.text)
            self.chats.open()
            chat = self.chats.get_from_msg(message)
            if chat.status == "select-classes":
                chat.reset_status()
                selection = self.parse_selection(message.text)
                chat.selection = selection
                self.chats.save()
                self.chats.close()
                await self.send_selection_set(chat, selection)
                print("selected classes", chat, message.text, selection)
            else:
                self.chats.close()
                if MOIN.search(message.text):
                    logger.debug("MOIN MOIN")
                    await self.send_message(message.chat.id, self.texts["MOIN"])
                else:
                    logger.debug("Unknown text")
                    await self.send_message(message.chat.id, self.texts["unknown"])
        else:
            await self.send_message(message.chat.id, self.texts["send-only-text"])

    async def all_callbacks(self, callback: asynctelebot.types.CallbackQuery):
        logger.info(f"{callback.message.chat.id} {str_from_timestamp(callback.message.date)} CALLBACK "
                    f"({callback.message.chat.first_name})")
        self.chats.open()
        chat = self.chats.get(callback.message.chat.id)
        if callback.data.startswith("setting-"):
            name, value_string = callback.data[8:].split("-", 1)
            values = self.available_settings[name]
            value = values[0] if str(values[0]) == value_string else values[1]
            if value != chat.get(name):
                chat.set(name, value)
                self.chats.save()
                self.chats.close()
                await self.answer_callback_query(callback.id, self.texts["settings"][name]["selected-" + value_string])
                await self.edit_message_text(self.create_settings_text(chat), callback.message.chat.id,
                                             callback.message.message_id, parse_mode="html",
                                             reply_markup=self.create_settings_keyboard(chat))
            else:
                self.chats.save()
                self.chats.close()


def run_bot_listener(logger_name, bot_listener_class, bot_texts_name, settings_command_key):
    import json
    from logging_tool import create_logger
    
    logger = create_logger(logger_name)

    with open("bot/settings.json", "r") as f:
        settings = json.load(f)
    logger.info("Starting bot...")
    with open("bot/texts.json") as f:
        texts_all = json.load(f)
    texts = texts_all["common"]
    texts.update(texts_all[bot_texts_name])
    texts = BotTexts(texts)
    with open("bot/secret.json") as f:
        bot = bot_listener_class(texts, settings["available_settings"], settings[settings_command_key], json.load(f)["token"], "data/student_chats.sqlite3")
    try:
        logger.info("Polling")
        bot.handler.polling(infinite=True, error_wait=10)
    finally:
        logger.error("Error occurred, saving and closing")
