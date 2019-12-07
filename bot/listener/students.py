from asynctelebot.methods import SendMessage

from bot.listener.base import SubstitutionsBotListener
from bot.listener.texts import BotTexts


class StudentBotListener(SubstitutionsBotListener):
    def __init__(self, bot, texts: BotTexts, available_settings, commands):
        super().__init__(bot, texts, available_settings, commands)

    def _create_selection_info_text(self, selection):
        return self.texts["settings-info-selected-class" if len(selection) == 1 else "settings-info-selected-classes"] \
            .format(", ".join(selection))

    def send_selection_set(self, chat_id, selection, was_selected_in_start_command=False):
        if was_selected_in_start_command:
            if "," not in selection:
                return SendMessage(chat_id, self.texts["class-automatically-set"].format(selection), parse_mode="html")
            else:
                return SendMessage(chat_id, self.texts["classes-automatically-set"].format(selection),
                                   parse_mode="html")
        else:
            if "," not in selection:
                return SendMessage(chat_id, self.texts["notify-about-class"].format(selection), parse_mode="html")
            else:
                return SendMessage(chat_id, self.texts["notify-about-classes"].format(selection), parse_mode="html")
