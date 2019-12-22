import logging

from bot.db.base import DatabaseBot, DatabaseChatList, DatabaseChat

logger = logging.getLogger()


class TeacherDatabaseBot(DatabaseBot):
    def __init__(self, api_token, db_connection):
        super().__init__(api_token, TeacherDatabaseChatList(db_connection, "teachers", self))


class TeacherDatabaseChatList(DatabaseChatList):
    def _chat_from_row(self, row):
        return TeacherDatabaseChat.from_row(self.connection, row, self.bot)

    def _new_chat(self, chat_id):
        return TeacherDatabaseChat(self.bot, self.connection, chat_id)


class TeacherDatabaseChat(DatabaseChat):
    @staticmethod
    def from_row(cursor, row, bot):
        return TeacherDatabaseChat(bot, cursor, *row)

    def set_selection_from_string(self, text: str):
        super().set_selection_from_string(text.upper())
