#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os.path
import sys
from functools import partial

from bot_utils import CustomAsyncTeleBot

dir = os.path.dirname(__file__)
os.chdir(dir)
sys.path.append(os.path.join(dir, "sitepackages/"))
import base64

import telebot

INFO_NAME_TO_GERMAN = {
    "news": "Nachrichten",
    "absent-classes": "abwesende Klassen",
    "absent-teachers": "abwesende Lehrer"
}


def start_bot(token):
    bot = CustomAsyncTeleBot(token, "data/chats.json")

    @bot.message_handler(commands=["start"])
    def start(message):
        help_(message)
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
                bot.chats.get(message.chat.id).selected_classes = selected_classes
                bot.chats.save()
                if len(selected_classes) == 1:
                    bot.send_message(message.chat.id, 'Die von dir auf der Webseite ausgewählte Klasse '
                                                      '<i>{}</i> wurde automatisch ausgewählt. Du kannst '
                                                      'die Auswahl mit dem /klassen-Befehl anpassen. '.format(
                        selected_classes[0]), parse_mode="html")
                else:
                    bot.send_message(message.chat.id, 'Die von dir auf der Webseite ausgewählte Klassen '
                                                      '<i>{}</i> wurden automatisch ausgewählt. Du '
                                                      'kannst die Auswahl mit dem /klassen-Befehl anpassen. '.format(
                        ", ".join(selected_classes)),
                                     parse_mode="html")
        except Exception:
            pass

    @bot.message_handler(commands=["help"])
    def help_(message):
        chat = bot.chats.get_from_msg(message)
        chat.reset_status()
        chat.send("Ich verschicke Nachrichten, wenn es neue Vertretungen auf dem Vertretungsplan des Gymnasiums am "
                  "Wall Verden gibt.\n "
                  "Folgende Befehle stehen zur Verfügung:\n"
                  "\n"
                  "/klassen - Klassen setzen, für die du benachrichtigt werden willst. Die Klassen müssen gesetzt "
                  "werden, damit der Bot "
                  "Nachrichten an dich verschicken kann.\n"
                  "/nachrichten - Einstellen, ob du über Nachrichten informiert werden willst\n"
                  "/abwesendeklassen - Einstellen, ob du über abwesende Klassen informiert werden willst\n"
                  "/abwesendelehrer - Einstellen, ob du über abwesende Lehrer informiert werden willst\n"
                  "/auswahl - Zeigt die Einstellungen: Die gewählten Klassen und ob über Nachrichten, abwesende "
                  "Lehrer oder abwesende "
                  "Klassen informiert werden soll.\n"
                  "/format - Einstellen, ob Vertretungen als Tabelle oder Text gesendet werden sollen\n"
                  "/reset - Löscht alle Daten, die diesem Chat zugeordnet sind\n"
                  "\n"
                  "Dieser Bot gehört zum Vertretungsplan unter gawvertretung.florianraediker.de und ist nicht "
                  "offiziell.\n "
                  "Alle Angaben ohne Gewähr. Es gibt keine Garantie, dass Benachrichtigungen zuverlässig verschickt "
                  "werden.\n")

    @bot.message_handler(commands=["klassen"])
    def select_classes(message):
        chat = bot.chats.get_from_msg(message)
        chat.status = "select-classes"
        chat.send('Schicke mir alle Klassen, für die du benachrichtigt werden willst, durch Kommata getrennt (z.B. '
                  '"6A, 11C").\n'
                  "Die Auswahl wird auf dem Server gespeichert und diesem Chat zugeordnet. ")

    @bot.message_handler(commands=["auswahl"])
    def show_selected_classes(message):
        chat = bot.chats.get(message.chat.id)
        chat.reset_status()
        if chat.selected_classes:
            message_text = "Du hast die Klassen <i>{}</i> ausgewählt. ".format(", ".join(chat.selected_classes))
        else:
            message_text = "Du hast noch keine Klassen ausgewählt. Wähle Klassen mit dem /klassen-Befehl aus. "
        selected_infos = []
        not_selected_infos = []
        for name in ("news", "absent-classes", "absent-teachers"):
            if chat.get("send-" + name, True):
                selected_infos.append(name)
            else:
                not_selected_infos.append(name)
        if selected_infos:
            message_text += "\nDu wirst über {} auf dem Vertretungsplan informiert. ".format(
                (", ".join(INFO_NAME_TO_GERMAN[name] for name in selected_infos[:-1]) + " und " +
                 INFO_NAME_TO_GERMAN[selected_infos[-1]]
                 if len(selected_infos) > 1 else INFO_NAME_TO_GERMAN[selected_infos[0]])
            )
        if not_selected_infos:
            message_text += "\nDu wirst nicht über {} auf dem Vertretungsplan informiert. ".format(
                (", ".join(INFO_NAME_TO_GERMAN[name] for name in not_selected_infos[:-1]) + " und " +
                 INFO_NAME_TO_GERMAN[not_selected_infos[-1]]
                 if len(not_selected_infos) > 1 else INFO_NAME_TO_GERMAN[not_selected_infos[0]])
            )
        chat.send(message_text, parse_mode="html")

    @bot.message_handler(commands=["reset"])
    def reset(message):
        bot.chats.reset_chat(message.chat.id)
        bot.chats.save()
        bot.send_message(message.chat.id, "Die diesem Chat zugeordneten Daten wurden gelöscht. ")

    @bot.message_handler(commands=["format"])
    def set_send_type(message):
        chat = bot.chats.get_from_msg(message)
        chat.reset_status()
        markup = telebot.types.InlineKeyboardMarkup(2)
        table_btn = telebot.types.InlineKeyboardButton("Tabelle", callback_data="set-format-table")
        text_btn = telebot.types.InlineKeyboardButton("Text", callback_data="set-format-text")
        markup.add(table_btn, text_btn)
        chat.send("Sollen Vertretungen als Text oder Tabelle gesendet werden? "
                  "Tabellen sind auf kleinen Displays schwerer zu lesen. ", reply_markup=markup)

    def set_send_base(message, name, name_german):
        chat = bot.chats.get_from_msg(message)
        chat.reset_status()
        if chat.get("send-{}".format(name), True):
            markup = telebot.types.InlineKeyboardMarkup(2)
            markup.add(telebot.types.InlineKeyboardButton(name_german + " nicht mehr senden",
                                                          callback_data="set-send-{}-n".format(name)))
            bot.send_message(message.chat.id,
                             "Im Moment informiere ich über {} auf dem Vertretungsplan. ".format(name_german),
                             reply_markup=markup)
        else:
            markup = telebot.types.InlineKeyboardMarkup(2)
            markup.add(telebot.types.InlineKeyboardButton("{} wieder senden".format(name_german.capitalize()),
                                                          callback_data="set-send-{}-y".format(name)))
            bot.send_message(message.chat.id,
                             "Im Moment informiere ich nicht über {} auf dem Vertretungsplan. ".format(name_german),
                             reply_markup=markup)

    set_send_news = bot.message_handler(
        commands=["nachrichten"])(partial(set_send_base, name="news", name_german="Nachrichten"))
    set_send_absent_classes = bot.message_handler(
        commands=["abwesendeklassen"])(partial(set_send_base, name="absent-classes", name_german="abwesende Klassen"))
    set_send_absent_teachers = bot.message_handler(
        commands=["abwesendelehrer"])(partial(set_send_base, name="absent-teachers", name_german="abwesende Lehrer"))

    @bot.message_handler(func=lambda m: True)
    def all_messages(message):
        chat = bot.chats.get_from_msg(message)
        if chat.status == "select-classes":
            chat.reset_status()
            selected_classes = []
            for selected_class in "".join(message.text.split()).split(","):
                if selected_class and selected_class not in selected_classes:
                    selected_classes.append(selected_class)
            chat.selected_classes = selected_classes
            bot.chats.save()
            if len(selected_classes) == 0:
                chat.status = "select-classes"
                chat.send("Bitte gib alle Klassen, für die du benachrichtigt werden willst, durch Kommata getrennt "
                          "ein. ")
            elif len(selected_classes) == 1:
                chat.send("Du wirst für die Klasse <i>{}</i> benachrichtigt. ".format(selected_classes[0]),
                          parse_mode="html")
            else:
                chat.send("Du wirst für die Klassen <i>{}</i> benachrichtigt. ".format(", ".join(selected_classes)),
                          parse_mode="html")
        else:
            bot.send_message(message.chat.id, "Keine Ahnung, was das heißen soll...")

    @bot.callback_query_handler(func=lambda call: True)
    def all_callbacks(callback):
        chat = bot.chats.get(callback.message.chat.id)
        if callback.data == "set-format-table":
            chat.send_type = "table"
            bot.send_message(callback.message.chat.id, "Vertretungen werden als Tabelle verschickt. ")
            bot.chats.save()
        elif callback.data == "set-format-text":
            chat.send_type = "text"
            bot.send_message(callback.message.chat.id, "Vertretungen werden als Text verschickt. ")
            bot.chats.save()
        elif callback.data.startswith("set-send-"):
            name = callback.data[9:-2]
            value = callback.data[-1] == "y"
            name_german = INFO_NAME_TO_GERMAN[name]
            if value != chat.get("send-" + name, True):
                chat.set("send-" + name, value)
                bot.send_message(callback.message.chat.id, "Du wirst {}über {} informiert. ".format(
                    ("nicht " if not value else ""), name_german))
                bot.chats.save()
            else:
                bot.send_message(callback.message.chat.id,
                                 "Du wirst bereits {}über {} informiert. ".format(("nicht " if not value else ""),
                                                                                  name_german))

    return bot
