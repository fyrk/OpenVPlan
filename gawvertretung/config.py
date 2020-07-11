import json

import logging

_LOGGER = logging.getLogger("gawvertretung")

_CONFIG = {}


def load(filepath="config.json", filepath_secret="secret_config.json"):
    global _CONFIG
    # noinspection PyBroadException
    try:
        with open(filepath, "r") as f:
            config = json.load(f)
            if type(config) == dict:
                _CONFIG.update(config)
        with open(filepath_secret, "r") as f:
            config = json.load(f)
            if type(config) == dict:
                _CONFIG.update(config)
    except Exception:
        _LOGGER.exception(f"Could not load config files '{filepath}' and '{filepath_secret}'")


load()


def get_str(key: str, default=""):
    try:
        return str(_CONFIG.get(key, default))
    except ValueError:
        return default


def get_bool(key: str, default=False):
    try:
        return bool(_CONFIG.get(key, default))
    except ValueError:
        return default


def get_int(key: str, default=0):
    try:
        return int(_CONFIG.get(key, default))
    except ValueError:
        return default
