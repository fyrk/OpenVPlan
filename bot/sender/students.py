from bot.db.students import StudentDatabaseChat
from bot.sender.base import BaseMessageSender, Day
from common.students import is_class_selected, split_class_name_lower


class StudentMessageSender(BaseMessageSender):
    async def _send_message_to(self, chat: StudentDatabaseChat, day: Day):
        self.logger.debug(f"Send message to student {chat}")
        message = self._build_message_info_text(chat, day)
        self.logger.debug(message)
        selection = [split_class_name_lower(name) for name in chat.get_parsed_selection()]
        self.logger.debug(f"selection is {selection}, substitutions: {day.substitutions}")
        substitutions = [(class_name, substitution_text)
                         for class_name, substitution_text in day.substitutions
                         if is_class_selected(class_name, selection)]
        self.logger.debug(f"{selection} {substitutions}")
        if len(selection) == 1 and len(substitutions) == 1 and \
                substitutions[0][0].lower() == (selection[0][0] + selection[0][1]).lower():
            message += substitutions[0][1]
        else:
            message += "\n".join(class_name + ":\n" + substitution_text
                                 for class_name, substitution_text in substitutions)
        self.logger.debug(message)
        if message:
            await chat.send_substitution(day.timestamp, day.date_info + message)
