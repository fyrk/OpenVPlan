from asynctelebot.methods import SendMessage

from bot.listener.base import SubstitutionsBotListener
from bot.listener.texts import BotTexts


class TeacherBotListener(SubstitutionsBotListener):
    def __init__(self, bot, texts: BotTexts, available_settings, commands):
        super().__init__(bot, texts, available_settings, commands)

    def _create_selection_info_text(self, selection):
        return self.texts["settings-info-selected-teacher-abbr"].format(selection)

    def send_selection_set(self, chat_id, selection, was_selected_in_start_command=False):
        if was_selected_in_start_command:
            return SendMessage(chat_id, self.texts["teacher-abbr-automatically-set"].format(selection),
                               parse_mode="html")
        else:
            return SendMessage(chat_id, self.texts["notify-about-teacher-abbr"].format(selection), parse_mode="html")
