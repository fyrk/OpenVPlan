import logging
import sqlite3

try:
    import mysql.connector
except ModuleNotFoundError:
    mysql = None


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

    def _execute(self, operation, table_name, args=(), try_again=True):
        try:
            self.cursor.execute(operation.format(table=table_name), args)
        except Exception:
            logger.exception(f"Database error: {repr(operation.format(table=table_name))} {repr(args)} {try_again}")
            if try_again:
                logger.info("Trying to reconnect")
                self.connection.close()
                self._connect()
                self._execute(operation, table_name, args, try_again=False)

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
        self._execute("SELECT * FROM {}", table_name)
        logger.info("all_chats...")
        for row in self.cursor.fetchall():
            logger.info(f"chat {row}")
            yield row

    def delete_chat(self, table_name, chat_id):
        raise NotImplementedError

    def set_sent_substitutions(self, table_name, sent_messages, chat_id):
        raise NotImplementedError

    def update_chat(self, table_name, key, value, chat_id):
        raise NotImplementedError


class MySQLConnection(BaseConnection):
    def _connect(self):
        self.connection = mysql.connector.connect(**self._connection_kwargs)
        self.connection.autocommit = True
        self.cursor = self.connection.cursor()

    def get_chat(self, table_name, chat_id):
        self._execute("SELECT * FROM {table} WHERE chat_id=%s", table_name, (chat_id,))
        return self.cursor.fetchone()

    def new_chat(self, table_name, chat_id: int, status: str, selection: str, send_news: int, send_absent_classes: int,
                 send_absent_teachers: int, sent_messages: str):
        self._execute("INSERT INTO {table} VALUES (%s,%s,%s,%s,%s,%s,%s)", table_name, (chat_id, status, selection,
                                                                                        send_news, send_absent_classes,
                                                                                        send_absent_teachers,
                                                                                        sent_messages))

    def delete_chat(self, table_name, chat_id):
        self._execute("DELETE FROM {table} WHERE chat_id=%s", table_name, chat_id)

    def set_sent_substitutions(self, table_name, sent_messages, chat_id):
        self._execute("UPDATE {table} SET sent_messages=%s WHERE chat_id=%s", table_name, (sent_messages, chat_id))

    def update_chat(self, table_name, key, value, chat_id):
        assert " " not in key
        self._execute("UPDATE {table} SET " + key + "=%s WHERE chat_id=%s", table_name, (value, chat_id))


class SQLiteConnection(BaseConnection):
    def _connect(self):
        self.connection = sqlite3.connect(**self._connection_kwargs)
        self.cursor = self.connection.cursor()

    def get_chat(self, table_name, chat_id):
        self._execute("SELECT * FROM {table} WHERE chat_id=?", table_name, (chat_id,))
        return self.cursor.fetchone()

    def new_chat(self, table_name, chat_id: int, status: str, selection: str, send_news: int, send_absent_classes: int,
                 send_absent_teachers: int, sent_messages: str):
        self._execute("INSERT INTO {table} VALUES (?,?,?,?,?,?,?)", table_name, (chat_id, status, selection, send_news,
                                                                                 send_absent_classes,
                                                                                 send_absent_teachers, sent_messages))

    def delete_chat(self, table_name, chat_id):
        self._execute("DELETE FROM {table} WHERE chat_id=?", table_name, (chat_id,))

    def set_sent_substitutions(self, table_name, sent_messages, chat_id):
        self._execute("UPDATE {table} SET sent_messages=? WHERE chat_id=?", table_name, (sent_messages, chat_id))

    def update_chat(self, table_name, key, value, chat_id):
        self._execute("UPDATE {table} SET " + key + "=? WHERE chat_id=?", table_name, (value, chat_id))


def get_connection(secret):
    try:
        connection = MySQLConnection(**secret["database_mysql"])
        logger.info("Using MySQL database")
        return connection
    except Exception:
        logger.exception("Using MySQL database failed")
        logger.info("Using SQLite database")
        connection = SQLiteConnection(**secret["database_sqlite"])
        return connection
