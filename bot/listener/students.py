from bot.listener.base import SubstitutionsBotListener
from bot.utils import BotTexts
from common.students import StudentSelectionHandler


class StudentBotListener(SubstitutionsBotListener):
    def __init__(self, texts: BotTexts, available_settings, commands, token, filename):
        super().__init__(texts, available_settings, commands, token, filename, StudentSelectionHandler)

    async def send_selection_set(self, chat, selection, was_selected_in_start_command=False):
        if was_selected_in_start_command:
            if len(selection) == 1:
                await chat.send(self.texts["classes-automatically-set"].format(selection[0]),
                                parse_mode="html")
            else:
                await chat.send(self.texts["classes-automatically-set"].format(", ".join(selection)),
                                parse_mode="html")
        else:
            if len(selection) == 1:
                await chat.send(self.texts["notify-about-class"].format(selection[0]), parse_mode="html")
            else:
                await chat.send(self.texts["notify-about-classes"].format(", ".join(selection)), parse_mode="html")
