from bot.listener.base import SubstitutionsBotListener
from bot.utils import BotTexts
from common.teachers import TeacherSelectionHandler


class StudentBotListener(SubstitutionsBotListener):
    def __init__(self, texts: BotTexts, available_settings, commands, token, filename):
        super().__init__(texts, available_settings, commands, token, filename, TeacherSelectionHandler)

    async def send_selection_set(self, chat, selection, was_selected_in_start_command=False):
        if was_selected_in_start_command:
            await chat.send(self.texts["teacher-abbr-automatically-set"].format(selection),
                            parse_mode="html")
        else:
            await chat.send(self.texts["notify-about-teacher-abbr"].format(selection[0]), parse_mode="html")
