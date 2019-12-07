import logging
import time


logger = logging.getLogger()


def get_connection(secret, tries_left=10, error=None):
    if tries_left == 0:
        raise error
    if True:  # sys.platform == "darwin":
        import sqlite3
        logger.info("USING SQLITE DATABASE")
        return sqlite3.connect(**secret["database_sqlite"])
    else:
        import mysql.connector
        try:
            logger.info("USING MYSQL DATABASE")
            return mysql.connector.connect(**secret["database_mysql"])
        except mysql.connector.errors.InterfaceError as e:
            time.sleep(10)
            return get_connection(secret, tries_left - 1, e)
