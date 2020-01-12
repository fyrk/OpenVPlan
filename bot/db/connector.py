import logging
import sqlite3

from common.utils import obfuscate_chat_id

logger = logging.getLogger()


class BaseConnection:
    def __init__(self, **connection_kwargs):
        self._connection_kwargs = connection_kwargs
        self._connect()

    def _connect(self):
        self.connection = None
        self.cursor = None
        raise NotImplementedError

    def close(self):
        self.connection.close()

    def _execute(self, operation, table_name, args=(), sensitive=None):
        def obfuscate_arg(arg, mode) -> str:
            if not mode:
                return str(arg)
            if mode == "obfuscate":
                return "*" * len(str(arg))
            if mode == "chat_id":
                return obfuscate_chat_id(arg)
            return "?"

        operation = operation.format(table=table_name)
        if len(args) != 0:
            if sensitive:
                args_info = "(" + ", ".join(obfuscate_arg(arg, s) for arg, s in zip(args, sensitive)) + ")"
            else:
                args_info = str(args)
        else:
            args_info = "()"
        logger.debug(f"DB: {repr(operation)} {args_info}")
        # noinspection PyBroadException
        try:
            self.cursor.execute(operation, args)
        except Exception:
            logger.exception(f"Database error: {repr(operation)} {args_info}")

    def try_create_table(self, table_name):
        self._execute("""CREATE TABLE IF NOT EXISTS {table} (
                            chat_id INTEGER primary key,
                            status TEXT,
                            selection TEXT,
                            send_news INTEGER,
                            send_absent_classes INTEGER,
                            send_absent_teachers INTEGER,
                            sent_messages TEXT)""", table_name)

    def get_chat(self, table_name, chat_id):
        raise NotImplementedError

    def new_chat(self, table_name, chat_id: int, status: str, selection: str, send_news: int, send_absent_classes: int,
                 send_absent_teachers: int, sent_messages: str):
        raise NotImplementedError

    def all_chats(self, table_name):
        self._execute("SELECT * FROM {table}", table_name)
        for row in self.cursor.fetchall():
            yield row

    def delete_chat(self, table_name, chat_id):
        raise NotImplementedError

    def set_sent_substitutions(self, table_name, sent_messages, chat_id):
        raise NotImplementedError

    def update_chat(self, table_name, key, value, chat_id):
        raise NotImplementedError


class SQLiteConnection(BaseConnection):
    def _connect(self):
        self.connection = sqlite3.connect(**self._connection_kwargs)
        self.cursor = self.connection.cursor()

    def get_chat(self, table_name, chat_id):
        self._execute("SELECT * FROM {table} WHERE chat_id=?", table_name, (chat_id,), ("chat_id",))
        return self.cursor.fetchone()

    def new_chat(self, table_name, chat_id: int, status: str, selection: str, send_news: int, send_absent_classes: int,
                 send_absent_teachers: int, sent_messages: str):
        self._execute("INSERT INTO {table} VALUES (?,?,?,?,?,?,?)", table_name,
                      (chat_id, status, selection, send_news, send_absent_classes, send_absent_teachers, sent_messages),
                      ("chat_id", False, False, False, False, False, False))

    def delete_chat(self, table_name, chat_id):
        self._execute("DELETE FROM {table} WHERE chat_id=?", table_name, (chat_id,), ("chat_id",))

    def set_sent_substitutions(self, table_name, sent_messages, chat_id):
        self._execute("UPDATE {table} SET sent_messages=? WHERE chat_id=?", table_name,
                      (sent_messages, chat_id), (False, "chat_id"))

    def update_chat(self, table_name, key, value, chat_id):
        self._execute("UPDATE {table} SET " + key + "=? WHERE chat_id=?", table_name,
                      (value, chat_id), ("obfuscate", "chat_id"))


def get_connection(secret):
    logger.info("Using SQLite database")
    connection = SQLiteConnection(**secret["database_sqlite"])
    return connection
