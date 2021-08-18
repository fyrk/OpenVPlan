import logging

import settings

s = settings.settings

s.DEBUG = True
s.PUBLIC_VAPID_KEY = "<REPLACE>"
s.PRIVATE_VAPID_KEY = "<REPLACE>"
s.VAPID_SUB = "<REPLACE>"
s.WEBPUSH_CONTENT_ENCODING = "aesgcm"

s.TELEGRAM_BOT_LOGGER_TOKEN = "<REPLACE>"
s.TELEGRAM_BOT_LOGGER_CHAT_ID = 0  # <REPLACE>
s.TELEGRAM_BOT_LOGGER_USE_FIXED_WIDTH = False
s.TELEGRAM_BOT_LOGGER_LEVEL = logging.WARNING

s.TEMPLATE_OPTIONS = {
    "plausible_domain": "<REPLACE_PLAUSIBLE-DOMAIN>",
    "plausible_js": "https://<REPLACE_PLAUSIBLE-DOMAIN>/js/plausible.outbound-links.js",
    "plausible_endpoint": "https://<REPLACE_PLAUSIBLE-DOMAIN>/api/event",
    "plausible_embed_code": """<iframe plausible-embed src="<REPLACE>" scrolling="no" frameborder="0" loading="lazy"></iframe>
<p id="plausible-ref">Stats powered by <a target="_blank" href="https://plausible.io">Plausible Analytics</a></p>
<script async src="https://<REPLACE_PLAUSIBLE-DOMAIN>/js/embed.host.js"></script>""",
    "ferien": True
}

s.ADDITIONAL_CSP_DIRECTIVES = {
    "script-src": "https://<REPLACE_PLAUSIBLE-DOMAIN>/js/embed.host.js",
    "frame-src": "https://<REPLACE_PLAUSIBLE-DOMAIN>/share/gawvertretung.florian-raediker.de",
}

s.DEFAULT_PLAN_ID = "students"
s.SUBSTITUTION_PLANS = {
    "students": {
        "crawler": {
            "name": "multipage",
            "options": {
                "url": "https://<REPLACE>/subst_{:03}.htm"
            }
        },
        "parser": {
            "name": "untis",
            "options": {
                "encoding": "iso-8859-1",
                "lesson_column": 3
            }
        },
        "background_updates": [
            # min     hour dom mon dow sec
            "  0       *    *   *   *   R",  # every hour all the time
            "15,30,45 5-22  *   *  1-5  R",  # all 15 minutes from 5-22 o'clock on weekdays
            "46-59     6    *   *  1-5  R",  # every minute on weekdays from 6:46 to 6:59
            "1-14,16-29,31-44,46-59 7 * * 1-5 R"  # every minute on weekdays from 7:01 to 7:59
        ],
        "template_options": {
            "title": "Schüler*innen",
            "keywords": "Schüler, Klassen, Schüler*innen",
            "supports_timetables": True,
            "table_headers": ["Kla", "Lehrer", "Vertr", "Stunde", "Fach", "Raum", "Vertr von", "Hinweis"],
            "original_data_link": "https://<REPLACE>/subst_{:03}.htm",
            "texts": {
                "select_heading": "Klassen auswählen",
                "select_text": "Einzelne Klassen können mit dem Lesezeichen-Symbol ausgewählt werden.<br>"
                               "Mehrere Klassen oder Klassen, für die es gerade keine Vertretungen gibt, können hier "
                               "ausgewählt werden:",
                "selection_help_text": "Mehrere Klassen durch Kommata trennen",
                "selection_all": "Alle Klassen",
                "notifications_info_all": "Du wirst für alle Klassen benachrichtigt. "
                                          "Wähle Klassen aus, um nur für bestimmte Klassen benachrichtigt zu werden."
            }
        }
    },
    "teachers": {
        "crawler": {
            "name": "multipage",
            "options": {
                "url": "https://<REPLACE>/subst_{:03}.htm"
            }
        },
        "parser": {
            "name": "untis",
            "options": {
                "encoding": "iso-8859-1",
                "lesson_column": 1,
                "class_column": 2,
                "group_name_is_class": False
            }
        },
        "background_updates": [
            # min     hour dom mon dow sec
            "  0       *    *   *   *   R",  # every hour all the time
            "15,30,45 5-22  *   *  1-5  R",  # all 15 minutes from 5-22 o'clock on weekdays
            "46-59     6    *   *  1-5  R",  # every minute on weekdays from 6:46 to 6:59
            "1-14,16-29,31-44,46-59 7 * * 1-5 R"  # every minute on weekdays from 7:01 to 7:59
        ],
        "template_options": {
            "title": "Lehrer*innen",
            "keywords": "Lehrer, Lehrer*innen",
            "supports_timetables": False,
            "table_headers": ["Vertr", "Stunde", "Klasse", "Lehrer*in", "Fach", "Raum", "Vertr von", "Hinweis"],
            "original_data_link": "https://<REPLACE>/subst_{:03}.htm",
            "texts": {
                "select_heading": "Kürzel auswählen",
                "select_text": "Einzelne Lehrer*innenkürzel können mit dem Lesezeichen-Symbol ausgewählt werden.<br>"
                               "Mehrere Kürzel oder Kürzel, für die es gerade keine Vertretungen gibt, können hier "
                               "ausgewählt werden:",
                "selection_help_text": "Mehrere Kürzel durch Kommata trennen",
                "selection_all": "Alle Vertretungen",
                "notifications_info_all": "Du wirst für alle Vertretungen benachrichtigt. Wähle Kürzel aus, um nur für "
                                          "bestimmte Kürzel benachrichtigt zu werden."
            }
        },
        "uppercase_selection": True
    }
}

s.ABOUT_HTML = """<h1>Impressum</h1>
<REPLACE>

<h1>Datenschutzerklärung</h1>
<REPLACE>
"""
