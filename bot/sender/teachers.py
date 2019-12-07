from bot.db.teachers import TeacherDatabaseChat
from bot.sender.base import BaseMessageSender, Day


class TeacherMessageSender(BaseMessageSender):
    async def _send_message_to(self, chat: TeacherDatabaseChat, day: Day):
        self.logger.debug(f"Send message to teacher {chat}")
        message = self._build_message_info_text(chat, day)
        selection = chat.get_parsed_selection().lower()
        substitutions = [substitution_text
                         for teacher_abbr, substitution_text in day.substitutions
                         if not teacher_abbr[1] and teacher_abbr[0].lower() == selection]
        self.logger.debug(f"{message} {selection} {substitutions}")
        if message or substitutions:
            await chat.send_substitution(day.timestamp, day.date_info + message + "\n".join(substitutions))
