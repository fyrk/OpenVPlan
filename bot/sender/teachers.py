from bot.db.teachers import TeacherDatabaseChat
from bot.sender.base import BaseMessageSender


class TeacherMessageSender(BaseMessageSender):
    async def _send_message_to(self, chat: TeacherDatabaseChat, day_timestamp, day):
        message = self._build_message_info_text(chat, day)
        selection = chat.get_parsed_selection().lower()
        substitutions = [substitution_text
                         for teacher_abbr, substitution_text in day.substitutions.items()
                         if not teacher_abbr[1] and teacher_abbr[0].lower() == selection]
        if message or substitutions:
            await chat.send_substitution(day_timestamp, day.date_info + message + "\n".join(substitutions))
