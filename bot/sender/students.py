from bot.db.students import StudentDatabaseChat
from bot.sender.base import BaseMessageSender
from common.students import is_class_selected, split_class_name_lower


class StudentMessageSender(BaseMessageSender):
    async def _send_message_to(self, chat: StudentDatabaseChat, day_timestamp, day):
        message = self._build_message_info_text(chat, day)
        selection = [split_class_name_lower(name) for name in chat.get_parsed_selection()]
        substitutions = [(class_name, substitution_text)
                         for class_name, substitution_text in day.substitutions.items()
                         if is_class_selected(class_name, selection)]
        if len(selection) == 1 and len(substitutions) == 1 and \
                substitutions[0][0].lower() == (selection[0][0] + selection[0][1]).lower():
            message += substitutions[0][1]
        else:
            message += "\n".join("\n" + class_name + ":\n" + substitution_text
                                 for class_name, substitution_text in substitutions)
        if message:
            await chat.send_substitution(day_timestamp, day.date_info + message)
