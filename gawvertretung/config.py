import json

import logging

_LOGGER = logging.getLogger("gawvertretung")

_CONFIG = {}


def load(filepath="config.json", filepath_secret="secret_config.json"):
    global _CONFIG
    for fp in (filepath, filepath_secret):
        # noinspection PyBroadException
        try:
            with open(fp, "r") as f:
                config = json.load(f)
                if type(config) == dict:
                    _CONFIG.update(config)
        except Exception:
            _LOGGER.warning(f"Could not load config file '{fp}'")


load()


def get(key: str, default=None):
    return _CONFIG.get(key, default)


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
