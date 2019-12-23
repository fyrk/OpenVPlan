from asynctelebot.methods import SendMessage
from asynctelebot.types import Message
from asynctelebot.utils import determine_message_content_type

from bot.listener.admin import Admin
from bot.listener.base import SubstitutionsBotListener
from bot.listener.texts import BotTexts


class StudentBotListener(SubstitutionsBotListener):
    def __init__(self, bot, texts: BotTexts, available_settings, commands):
        super().__init__(bot, texts, available_settings, commands)
        self.admin_handler = Admin(self.bot.chats.connection)

    async def all_messages(self, message: Message):
        message_type = determine_message_content_type(message)
        if message.from_.id == 854107292 and message_type == "text":
            if message.text.startswith("/admin"):
                if not message.text.startswith("/admin"):
                    text = "Admin command must start with '/admin'"
                else:
                    text = self.admin_handler.handle_command(message.text[7:])
                return SendMessage(854107292, text)
            elif message.text.startswith("/raise_error"):
                raise ValueError("Just an error for testing...")
        return await super().all_messages(message)

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
