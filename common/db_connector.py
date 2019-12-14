import logging


logger = logging.getLogger()


class COMMANDS_SQLITE:
    GET_CHAT = """SELECT * FROM {} WHERE chat_id=?"""
    NEW_CHAT = """INSERT INTO {} VALUES (?,?,?,?,?,?,?)"""
    DELETE_CHAT = """DELETE FROM {} WHERE chat_id=?"""
    SET_SENT_SUBSTITUTIONS = "UPDATE {} SET sent_messages=? WHERE chat_id=?"
    UPDATE_CHAT = "UPDATE {} SET {}=? WHERE chat_id=?"


class COMMANDS_MySQL:
    GET_CHAT = """SELECT * FROM {} WHERE chat_id=%s"""
    NEW_CHAT = """INSERT INTO {} VALUES (%s,%s,%s,%s,%s,%s,%s)"""
    DELETE_CHAT = """DELETE FROM {} WHERE chat_id=%s"""
    SET_SENT_SUBSTITUTIONS = "UPDATE {} SET sent_messages=%s WHERE chat_id=%s"
    UPDATE_CHAT = "UPDATE {} SET {}=%s WHERE chat_id=%s"


def get_connection(secret):
    try:
        import mysql.connector
        connection = mysql.connector.connect(**secret["database_mysql"])
        logger.info("Using MySQL database")
        return connection, COMMANDS_MySQL
    except Exception:
        import sqlite3
        logger.exception("Using MySQL database failed")
        logger.info("Using MySQL database")
        connection = sqlite3.connect(**secret["database_sqlite"])
        return connection, COMMANDS_SQLITE
