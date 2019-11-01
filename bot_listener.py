#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import base64
import datetime
import json
import os
import random
import re

import asynctelebot
from asynctelebot.utils import determine_message_content_type

import bot_utils

os.chdir(os.path.dirname(__file__))

with open("bot_settings.json", "r") as f:
    SETTINGS = json.load(f)

with open("bot_texts.json", "r") as f:
    TEXTS = {}
    for key, value in json.load(f).items():
        if type(value) == list:
            TEXTS[key] = "\n".join(value)
        elif type(value) == dict and value.get("_random", False):
            choices = []
            weights = []
            for choice, weight in value.items():
                choices.append(choice)
                weights.append(weight)
            TEXTS[key] = (choices, weights)
        else:
            TEXTS[key] = value


MOIN = re.compile(r"\bmoin\b", re.IGNORECASE)


def random_text(name):
    return random.choices(TEXTS[name][0], TEXTS[name][1])[0]


def upper_first(string):
    return string[0].upper() + string[1:]


def str_from_timestamp(timestamp):
    return datetime.datetime.fromtimestamp(timestamp).strftime("%H:%M:%S")


def start_bot(token):
    bot = bot_utils.CustomBot(token, "data/chats.sqlite3")

    handler = asynctelebot.UpdateHandler(bot)

    handler.add_restriction_allowed_language_codes("de", help_text='Sorry, this bot is only for users with language '
                                                                   'code "de"')

    @handler.subscribe_message(commands=SETTINGS["commands"]["start"])
    async def start(message):
        logger.info(f"{message.chat.id} {str_from_timestamp(message.date)} COMMAND /start ({message.from_.first_name})")
        await help_(message)
        try:
            text = message.text.strip()
            if len(text) % 4 != 0:
                text += (4 - len(text) % 4) * "="
            selected_classes_string = base64.b64decode(text[7:]).decode("utf-8")
            selected_classes = []
            for selected_class in "".join(selected_classes_string.split()).split(","):
                if selected_class and selected_class not in selected_classes:
                    selected_classes.append(selected_class)
            if selected_classes:
                bot.chats.open()
                chat = bot.chats.get_from_msg(message)
                chat.selected_classes = selected_classes
                bot.chats.save()
                bot.chats.close()
                if len(selected_classes) == 1:
                    await chat.send(TEXTS["classes-automatically-set"].format(selected_classes[0]), parse_mode="html")
                else:
                    await chat.send(TEXTS["classes-automatically-set"].format(", ".join(selected_classes)),
                                    parse_mode="html")
        except Exception:
            pass

    @handler.subscribe_message(commands=SETTINGS["commands"]["help"])
    async def help_(message):
        logger.info(f"{message.chat.id} {str_from_timestamp(message.date)} COMMAND /help ({message.from_.first_name})")
        bot.chats.open()
        chat = bot.chats.get_from_msg(message)
        chat.reset_status()
        bot.chats.save()
        bot.chats.close()
        await chat.send(TEXTS["help"])

    @handler.subscribe_message(commands=SETTINGS["commands"]["select-classes"])
    async def select_classes(message):
        logger.info(f"{message.chat.id} {str_from_timestamp(message.date)} COMMAND /klassen "
                    f"({message.from_.first_name})")
        bot.chats.open()
        chat = bot.chats.get_from_msg(message)
        chat.status = "select-classes"
        bot.chats.save()
        bot.chats.close()
        await chat.send(TEXTS["send-classes-for-selection"])

    def create_settings_keyboard(chat):
        markup = asynctelebot.types.InlineKeyboardMarkup()
        for setting, values in SETTINGS["settings"].items():
            print(setting, values)
            value = str(values[0]) if chat.get(setting) == values[1] else str(values[1])
            markup.add_row(asynctelebot.types.InlineKeyboardButton(TEXTS["settings"][setting][value],
                                                                   callback_data="setting-" + setting + "-" + value))
        return markup

    def create_settings_text(chat):
        enabled = []
        disabled = []
        for name in ("news", "absent_classes", "absent_teachers"):
            if chat.get("send_" + name):
                enabled.append(name)
            else:
                disabled.append(name)
        if chat.selected_classes:
            message = TEXTS["settings-info-selected-class" if len(chat.selected_classes) == 1 else "settings-info-selected-classes"].format(", ".join(chat.selected_classes))
        else:
            message = TEXTS["settings-info-no-classes-selected"]
        if enabled:
            if len(enabled) == 1:
                message += TEXTS["settings-info-enabled"].format(TEXTS[enabled[0]])
            else:
                message += TEXTS["settings-info-enabled"].format(", ".join(TEXTS[name] for name in enabled[:-1]) +
                                                                 TEXTS["and"] + TEXTS[enabled[-1]])
        if disabled:
            if len(disabled) == 1:
                message += TEXTS["settings-info-disabled"].format(TEXTS[disabled[0]])
            else:
                message += TEXTS["settings-info-disabled"].format(", ".join(TEXTS[name] for name in disabled[:-1]) +
                                                                  TEXTS["and"] + TEXTS[disabled[-1]])
        message += TEXTS["setting-info-format"].format(TEXTS[chat.get("send_format")])
        return message

    @handler.subscribe_message(commands=SETTINGS["commands"]["settings"])
    async def settings(message: asynctelebot.Message):
        logger.info(f"{message.chat.id} {str_from_timestamp(message.date)} COMMAND /einst ({message.from_.first_name})")
        bot.chats.open()
        chat = bot.chats.get_from_msg(message)
        chat.reset_status()
        bot.chats.save()
        bot.chats.close()
        await chat.send(create_settings_text(chat), parse_mode="html", reply_markup=create_settings_keyboard(chat))

    @handler.subscribe_message(commands=SETTINGS["commands"]["reset"])
    async def reset(message):
        logger.info(f"{message.chat.id} {str_from_timestamp(message.date)} COMMAND /reset ({message.from_.first_name})")
        bot.chats.open()
        bot.chats.reset_chat(message.chat.id)
        bot.chats.save()
        bot.chats.close()
        logger.debug("Reset successful for chat id '" + str(message.chat.id) + "'")
        await bot.send_message(message.chat.id, TEXTS["reset-successful"])

    @handler.subscribe_message()
    async def all_messages(message: asynctelebot.Message):
        logger.info(f"{message.chat.id} {str_from_timestamp(message.date)} ALL MESSAGES ({message.from_.first_name})")
        if determine_message_content_type(message) == "text":
            logger.debug("Message: " + message.text)
            bot.chats.open()
            chat = bot.chats.get_from_msg(message)
            if chat.status == "select-classes":
                chat.reset_status()
                selected_classes = []
                for selected_class in "".join(message.text.split()).split(","):
                    if selected_class and selected_class not in selected_classes:
                        selected_classes.append(selected_class)
                chat.selected_classes = selected_classes
                bot.chats.save()
                bot.chats.close()
                if len(selected_classes) == 0:
                    chat.status = "select-classes"
                    await chat.send(TEXTS["send-classes-for-selection-wrong"])
                elif len(selected_classes) == 1:
                    await chat.send(TEXTS["notify-about-class"].format(selected_classes[0]), parse_mode="html")
                else:
                    await chat.send(TEXTS["notify-about-classes"].format(", ".join(selected_classes)),
                                    parse_mode="html")
            else:
                bot.chats.close()
                if MOIN.search(message.text):
                    logger.debug("MOIN MOIN")
                    await bot.send_message(message.chat.id, "Moin Moin")
                else:
                    logger.debug("Unknown text")
                    await bot.send_message(message.chat.id, random_text("unknown"))
        else:
            await bot.send_message(message.chat.id, TEXTS["send-only-text"])

    @handler.subscribe_callback_query(custom_filter=lambda c: True)
    async def all_callbacks(callback: asynctelebot.types.CallbackQuery):
        logger.info(f"{callback.message.chat.id} {str_from_timestamp(callback.message.date)} CALLBACK "
                    f"({callback.message.chat.first_name})")
        bot.chats.open()
        chat = bot.chats.get(callback.message.chat.id)
        if callback.data.startswith("setting-"):
            name, value_string = callback.data[8:].split("-", 1)
            values = SETTINGS["settings"][name]
            value = values[0] if str(values[0]) == value_string else values[1]
            if value != chat.get(name):
                chat.set(name, value)
                bot.chats.save()
                bot.chats.close()
                await bot.answer_callback_query(callback.id, TEXTS["settings"][name]["selected-" + value_string])
                await bot.edit_message_text(create_settings_text(chat), callback.message.chat.id,
                                            callback.message.message_id, parse_mode="html",
                                            reply_markup=create_settings_keyboard(chat))
            else:
                bot.chats.save()
                bot.chats.close()

    return bot, handler


if __name__ == "__main__":
    import json
    from logging_tool import create_logger

    logger = create_logger("bot-listener")
    bot_utils.logger = logger
    logger.info("Starting bot...")
    with open("secret.json") as f:
        bot, handler = start_bot(json.load(f)["token"])
    try:
        logger.info("Polling")
        handler.polling(infinite=True, error_wait=10)
    finally:
        logger.error("Error occurred, saving and closing")
