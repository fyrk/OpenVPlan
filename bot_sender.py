import asyncio
import hashlib
import json
import os
import pickle
import time
from collections import deque

from watchdog.events import FileSystemEventHandler
from watchdog.observers import Observer

import bot_utils
from logging_tool import create_logger
from substitution_utils import *

os.chdir(os.path.dirname(__file__))


logger = None

last_status = None


class EventHandler(FileSystemEventHandler):
    def on_modified(self, event):
        if event.src_path == "data/substitutions/substitutions.pickle":
            on_substitutions_modified()

    def on_created(self, event):
        if event.src_path == "data/substitutions/substitutions.pickle":
            on_substitutions_modified()


def on_substitutions_modified():
    global last_status
    with open("secret.json", "r") as f:
        bot = bot_utils.CustomBot(json.load(f)["token"], "data/chats.sqlite3")
    while True:
        try:
            with open("data/substitutions/substitutions.pickle", "rb") as f:
                data_status, data = pickle.load(f)
        except EOFError:
            time.sleep(0.1)
        else:
            break
    if data_status != last_status:
        last_status = data_status
        asyncio.run(send_bot_notifications(bot, data))
        bot.chats.close()


async def send_bot_notifications(bot, data):
    with open("data/sent_messages.json", "r") as f:
        sent_messages = json.load(f)
    sent_substitutions = deque(sent_messages["substitutions"], maxlen=200)
    sent_news = deque(sent_messages["news"], maxlen=20)
    sent_absent_classes = deque(sent_messages["absent-classes"], maxlen=20)
    sent_absent_teachers = deque(sent_messages["absent-teachers"], maxlen=20)

    current_timestamp = create_date_timestamp(datetime.datetime.now().strftime("%d.%m.%Y"))
    bot.chats.open()
    for day_timestamp, day in data.items():
        if day_timestamp >= current_timestamp:
            tasks = []
            for t in send_day_news(bot, sent_news, sent_absent_classes, sent_absent_teachers, day_timestamp, day):
                tasks.append(asyncio.create_task(t))
            if tasks:
                await asyncio.wait(tasks)

            for class_name, class_substitutions in day["substitutions"].items():
                for t in send_substitution_notification(bot, sent_substitutions, day_timestamp, day, class_name,
                                                        class_substitutions):
                    tasks.append(asyncio.create_task(t))
            if tasks:
                await asyncio.wait(tasks)

    with open("data/sent_messages.json", "w") as f:
        json.dump({
            "substitutions": list(sent_substitutions),
            "news": list(sent_news),
            "absent-classes": list(sent_absent_classes),
            "absent-teachers": list(sent_absent_teachers)
        }, f)
    bot.chats.save()
    bot.chats.close()


def send_day_news(bot, sent_news, sent_absent_classes, sent_absent_teachers, day_timestamp, day):
    logger.info("Send day news")
    try:
        if "news" in day or "absent-classes" in day or "absent-teachers" in day:
            texts = {}
            if "news" in day:
                news_hash = hashlib.sha1((day["date"] + "-" + day["news"]).encode()).hexdigest()
                if news_hash not in sent_news:
                    texts["news"] = day["news"].replace("<br>", "\n").replace("\n\r", "\n").replace("<br/>", "\n")
                    if "\n" in texts:
                        texts["news"] += "\n"
                    sent_news.append(news_hash)
            if "absent-classes" in day:
                absent_classes_hash = hashlib.sha1((day["date"] + "-" + day["absent-classes"]).encode()).hexdigest()
                if absent_classes_hash not in sent_absent_classes:
                    texts["absent_classes"] = day["absent-classes"]
                    sent_absent_classes.append(absent_classes_hash)
            if "absent-teachers" in day:
                absent_teachers_hash = hashlib.sha1((day["date"] + "-" + day["absent-teachers"]).encode()).hexdigest()
                if absent_teachers_hash not in sent_absent_teachers:
                    texts["absent_teachers"] = day["absent-teachers"]
                    sent_absent_teachers.append(absent_teachers_hash)

            name2text = {
                "news": "Nachrichten",
                "absent_classes": "Abwesende Klassen",
                "absent_teachers": "Abwesende Lehrer"
            }
            message_base = " für {}, {}, Woche {}: \n".format(day["day_name"], day["date"], day["week"])
            for chat in bot.chats.all_chats():
                selected_information = [(name, texts[name]) for name in
                                        ("news", "absent_classes", "absent_teachers")
                                        if chat.get("send_" + name) and name in texts]
                if selected_information:
                    if len(selected_information) == 1:
                        yield chat.send_substitution(day_timestamp, name2text[selected_information[0][0]] +
                                                     message_base + selected_information[0][1])
                    else:
                        message = "Informationen" + message_base
                        for name, info in selected_information:
                            message += name2text[name] + ": " + info + "\n"
                        yield chat.send_substitution(day_timestamp, message.rstrip(), parse_mode="html")
    except Exception:
        logger.exception("Sending news failed")


def create_substitution_messages(day, class_name, substitutions):
    message_base = "Vertretungen für {}, {}, Woche {}: \nKlasse {}: \n".format(day["day_name"],
                                                                               day["date"],
                                                                               day["week"],
                                                                               class_name)
    message_text = message_base
    table_row_lengths = [1, 1, 1, 1, 1, 2, 1]
    for s in substitutions:
        for i in range(7):
            length = len(s[i])
            if length > table_row_lengths[i]:
                table_row_lengths[i] = length

    message_table = message_base + '<pre>| {:^{}} | {:^{}} | {:^{}} | ' \
                                   '{:^{}} | {:^{}} | {:^{}} | ' \
                                   '{:^{}} |\n'.format("L", table_row_lengths[0], "V", table_row_lengths[1],
                                                       "S", table_row_lengths[2], "F", table_row_lengths[3],
                                                       "R", table_row_lengths[4], "Vv", table_row_lengths[5],
                                                       "H", table_row_lengths[6])

    for substitution in substitutions:
        # MESSAGE TEXT
        if ("---" in substitution[1] or "\xa0" in substitution[1] or not substitution[1]) \
                and "---" in substitution[3] and "---" in substitution[4]:  # \xa0 is nbsp
            if substitution[0].strip():
                lehrer = "bei {} ".format(substitution[0])
            else:
                lehrer = ""
            if "---" in substitution[1]:
                message_text += "Die {}. Stunde {}fällt aus".format(substitution[2], lehrer)
            else:
                message_text += "Die {}. Stunde {}findet nicht statt".format(substitution[2], lehrer)
        elif substitution[0] == substitution[1]:
            if substitution[0].strip():
                lehrer = "bei {} ".format(substitution[0])
            else:
                lehrer = ""
            if substitution[3].strip():
                fach = "{} ".format(substitution[3])
            else:
                fach = ""
            message_text += "Die {}. Stunde {}{}findet in {} statt".format(substitution[2], fach, lehrer,
                                                                           substitution[4])
        else:
            if substitution[0].strip():
                lehrer = "von {} ".format(substitution[0])
            else:
                lehrer = ""
            if substitution[3].strip():
                fach = "{} ".format(substitution[3])
            else:
                fach = ""
            if substitution[1].strip():
                vertreter = "durch {} ".format(substitution[1])
            else:
                vertreter = ""
            message_text += "Die {}. Stunde {}{}wird {}in {} vertreten".format(substitution[2], fach,
                                                                               lehrer, vertreter,
                                                                               substitution[4])
        if substitution[5].strip() and substitution[5].strip() != "&nbsp;":
            if substitution[6].strip() and substitution[6].strip() != "&nbsp;":
                message_text += " (Vertr. von {}, {})".format(substitution[5], substitution[6])
            else:
                message_text += " (Vertr. von {})".format(substitution[5])
        else:
            if substitution[6].strip() and substitution[6].strip() != "&nbsp;":
                message_text += " ({})".format(substitution[6])
        message_text += ".\n"

        # MESSAGE TABLE
        message_table += "| {:^{}} | {:^{}} | " \
                         "{:^{}} | {:^{}} | " \
                         "{:^{}} | {:^{}} | " \
                         "{:^{}} |\n".format(substitution[0], table_row_lengths[0],
                                             substitution[1], table_row_lengths[1],
                                             substitution[2], table_row_lengths[2],
                                             substitution[3], table_row_lengths[3],
                                             substitution[4], table_row_lengths[4],
                                             substitution[5], table_row_lengths[5],
                                             substitution[6], table_row_lengths[6]
                                             )
    message_table += "</pre>"
    return message_text, message_table


def send_substitution_notification(bot, sent_substitutions, day_timestamp, day, class_name, substitutions):
    logger.info("Sending substitution notifications")
    try:
        new_substitutions = []
        for substitution in substitutions:
            substitution_hash = hashlib.sha1(".".join((str(day_timestamp), class_name, *substitution)).encode()
                                             ).hexdigest()
            if substitution_hash not in sent_substitutions:
                sent_substitutions.append(substitution_hash)
                new_substitutions.append(substitution)

        if new_substitutions:
            message_text, message_table = create_substitution_messages(day, class_name, new_substitutions)

            for chat in bot.chats.all_chats():
                if chat.selected_classes:
                    if any(do_class_names_match(class_name, split_class_name(selected_class_name))
                           for selected_class_name in chat.selected_classes):
                        if chat.send_format == "text":
                            yield chat.send_substitution(day_timestamp, message_text.strip(), parse_mode="html")
                        else:
                            yield chat.send_substitution(day_timestamp, message_table.strip(), parse_mode="html")
    except Exception:
        logger.exception("Sending substitution notifications failed")


if __name__ == "__main__":
    logger = create_logger("bot-sender")
    bot_utils.logger = logger
    event_handler = EventHandler()
    observer = Observer()
    observer.schedule(event_handler, "data/substitutions")
    observer.start()
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        observer.stop()
    observer.join()
