#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import base64
import datetime
import json
import os
import random
import re
from functools import partial

import asynctelebot
from asynctelebot.utils import determine_message_content_type

import bot_utils

os.chdir(os.path.dirname(__file__))


with open("bot_texts.json", "r") as f:
    TEXTS = {}
    for key, value in json.load(f).items():
        if type(value) == list:
            TEXTS[key] = "\n".join(value)
        elif type(value) == dict:
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


INFO_NAME_TO_GERMAN = {
    "news": TEXTS["news"],
    "absent_classes": TEXTS["absent-classes"],
    "absent_teachers": TEXTS["absent-teachers"]
}


def upper_first(string):
    return string[0].upper() + string[1:]


def str_from_timestamp(timestamp):
    return datetime.datetime.fromtimestamp(timestamp).strftime("%H:%M:%S")


def start_bot(token):
    bot = bot_utils.CustomBot(token, "data/chats.sqlite3")

    handler = asynctelebot.UpdateHandler(bot)

    handler.add_restriction_allowed_language_codes("de", help_text='Sorry, this bot is only for users with language '
                                                                   'code "de"')

    @handler.subscribe_message(commands=["start"])
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

    @handler.subscribe_message(commands=["help"])
    async def help_(message):
        logger.info(f"{message.chat.id} {str_from_timestamp(message.date)} COMMAND /help ({message.from_.first_name})")
        bot.chats.open()
        chat = bot.chats.get_from_msg(message)
        chat.reset_status()
        bot.chats.save()
        bot.chats.close()
        await chat.send(TEXTS["help"])

    @handler.subscribe_message(commands=["klassen"])
    async def select_classes(message):
        logger.info(f"{message.chat.id} {str_from_timestamp(message.date)} COMMAND /klassen "
                    f"({message.from_.first_name})")
        bot.chats.open()
        chat = bot.chats.get_from_msg(message)
        chat.status = "select-classes"
        bot.chats.save()
        bot.chats.close()
        await chat.send(TEXTS["send-classes-for-selection"])

    @handler.subscribe_message(commands=["auswahl"])
    async def show_settings(message: asynctelebot.Message):
        logger.info(f"{message.chat.id} {str_from_timestamp(message.date)} COMMAND /auswahl "
                    f"({message.from_.first_name})")
        bot.chats.open()
        chat = bot.chats.get(message.chat.id)
        bot.chats.close()
        chat.reset_status()
        if chat.selected_classes:
            message_text = TEXTS["selected-classes"].format(", ".join(chat.selected_classes))
        else:
            message_text = TEXTS["no-classes-selected"]
        selected_infos = []
        not_selected_infos = []
        for name in ("news", "absent_classes", "absent_teachers"):
            if chat.get("send_" + name):
                selected_infos.append(name)
            else:
                not_selected_infos.append(name)
        if selected_infos:
            message_text += TEXTS["are-notified-about"].format(
                (", ".join(INFO_NAME_TO_GERMAN[name] for name in selected_infos[:-1]) + " und " +
                 INFO_NAME_TO_GERMAN[selected_infos[-1]]
                 if len(selected_infos) > 1 else INFO_NAME_TO_GERMAN[selected_infos[0]])
            )
        if not_selected_infos:
            message_text += TEXTS["not-notified-about"].format(
                (", ".join(INFO_NAME_TO_GERMAN[name] for name in not_selected_infos[:-1]) + " und " +
                 INFO_NAME_TO_GERMAN[not_selected_infos[-1]]
                 if len(not_selected_infos) > 1 else INFO_NAME_TO_GERMAN[not_selected_infos[0]])
            )
        await chat.send(message_text, parse_mode="html")

    @handler.subscribe_message(commands=["reset"])
    async def reset(message):
        logger.info(f"{message.chat.id} {str_from_timestamp(message.date)} COMMAND /reset ({message.from_.first_name})")
        bot.chats.open()
        bot.chats.reset_chat(message.chat.id)
        bot.chats.save()
        bot.chats.close()
        logger.debug("Reset successful for chat id '" + str(message.chat.id) + "'")
        await bot.send_message(message.chat.id, TEXTS["reset-successful"])

    @handler.subscribe_message(commands=["format"])
    async def set_send_type(message):
        logger.info(f"{message.chat.id} {str_from_timestamp(message.date)} COMMAND /format "
                    f"({message.from_.first_name})")
        bot.chats.open()
        chat = bot.chats.get_from_msg(message)
        chat.reset_status()
        bot.chats.save()
        bot.chats.close()
        markup = asynctelebot.types.InlineKeyboardMarkup()
        markup.add_row(asynctelebot.types.InlineKeyboardButton(TEXTS["table"], callback_data="set-format-table"),
                       asynctelebot.types.InlineKeyboardButton(TEXTS["text"], callback_data="set-format-text"))
        await chat.send(TEXTS["send-table-or-text"], reply_markup=markup)

    async def set_send_base(message, name, name_german):
        logger.info(f"{message.chat.id} {str_from_timestamp(message.date)} COMMAND /set-send {name} "
                    f"({message.from_.first_name})")
        bot.chats.open()
        chat = bot.chats.get_from_msg(message)
        chat.reset_status()
        bot.chats.close()
        if chat.get("send_{}".format(name)):
            markup = asynctelebot.types.InlineKeyboardMarkup()
            markup.add_row(asynctelebot.types.InlineKeyboardButton(upper_first(name_german) + " nicht mehr senden",
                                                                   callback_data="set-send-{}-n".format(name)))
            await chat.send(TEXTS["notifying"].format(name_german),
                            reply_markup=markup)
        else:
            markup = asynctelebot.types.InlineKeyboardMarkup()
            markup.add_row(asynctelebot.types.InlineKeyboardButton(upper_first(name_german) + " wieder senden",
                                                                   callback_data="set-send-{}-y".format(name)))
            await chat.send(TEXTS["not-notifying"].format(name_german),
                            reply_markup=markup)

    # noinspection PyUnusedLocal
    set_send_news = handler.subscribe_message(commands=["nachrichten"])(partial(set_send_base,
                                                                                name="news",
                                                                                name_german=TEXTS["news"]))
    # noinspection PyUnusedLocal,SpellCheckingInspection
    set_send_absent_classes = handler.subscribe_message(
        commands=["abwesendeklassen"])(partial(set_send_base,
                                               name="absent_classes",
                                               name_german=TEXTS["absent-classes"]))
    # noinspection PyUnusedLocal,SpellCheckingInspection
    set_send_absent_teachers = handler.subscribe_message(
        commands=["abwesendelehrer"])(partial(set_send_base,
                                              name="absent_teachers",
                                              name_german=TEXTS["absent-teachers"]))

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
        if callback.data == "set-format-table":
            chat.send_type = "table"
            bot.chats.save()
            bot.chats.close()
            await bot.answer_callback_query(callback.id, TEXTS["substitutions-sent-as-table"])
        elif callback.data == "set-format-text":
            chat.send_type = "text"
            bot.chats.save()
            bot.chats.close()
            await bot.answer_callback_query(callback.id, TEXTS["substitutions-sent-as-text"])
        elif callback.data.startswith("set-send-"):
            name = callback.data[9:-2]
            value = callback.data[-1] == "y"
            name_german = INFO_NAME_TO_GERMAN[name]
            if value != chat.get("send_" + name):
                chat.set("send_" + name, value)
                bot.chats.save()
                bot.chats.close()
                await bot.answer_callback_query(callback.id,
                                                TEXTS["will-be-notified-about" if value else "wont-be-notified-about"]
                                                .format(name_german))
            else:
                bot.chats.close()
                await bot.answer_callback_query(callback.id,
                                                TEXTS["already-notified-about" if value else
                                                      "already-not-notified-about"]
                                                .format(name_german))

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
