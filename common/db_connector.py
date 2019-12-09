import logging


logger = logging.getLogger()


def get_connection(secret):
    try:
        import mysql.connector
        logger.info("Try to connect to MySQL")
        return mysql.connector.connect(**secret["database_mysql"])
    except Exception:
        import sqlite3
        logger.exception("Using MySQL database failed, using SQLITE instead")
        return sqlite3.connect(**secret["database_sqlite"])
