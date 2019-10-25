import logging
import sys
import time


def create_logger(logging_type):
    logger = logging.getLogger()
    logger.setLevel(logging.DEBUG)
    log_formatter = logging.Formatter("{asctime} [{levelname:^8}]: {message}", "%Y.%m.%e %H:%M:%S",
                                      style="{")
    file_logger = logging.FileHandler(time.strftime("logs/" + logging_type + "/log-%Y.%m.%e_%H-%M-%S.txt"))
    file_logger.setFormatter(log_formatter)
    logger.addHandler(file_logger)
    stdout_logger = logging.StreamHandler(sys.stdout)
    stdout_logger.setFormatter(log_formatter)
    logger.addHandler(stdout_logger)
    return logger
