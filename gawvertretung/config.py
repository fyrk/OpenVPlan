import json

from gawvertretung import logger

_LOGGER = logger.get_logger()

# Default configuration, overridden by config.json and secret_config.json
_CONFIG = {
    "host": "localhost",
    "port": 8080,
    "is_proxied": False,
    "logfile": "gawvertretung.log",
    "data_dir": "data/",
    "user_agent": "GaWVertretungBot/{version} (+https://gawvertretung.florian-raediker.de) {server_software}",
    "template404": "error-404.min.html",
    "template500": "error-500-students.min.html",

    "include_outdated_substitutions": False,
    "dev": False,

    "default_plan": None,
    "substitution_plans": None
}


def load(filepath="config.json", filepath_secret="secret_config.json"):
    for fp in (filepath, filepath_secret):
        # noinspection PyBroadException
        try:
            with open(fp, "r") as f:
                try:
                    config = json.load(f)
                    if type(config) != dict:
                        raise json.JSONDecodeError("Not a JSON object", "", 0)
                except json.JSONDecodeError:
                    _LOGGER.exception(f"Could not load config file '{fp}'")
                    continue
                _CONFIG.update(config)
        except Exception:
            _LOGGER.exception(f"Could not load config file '{fp}'")
        else:
            _LOGGER.info(f"Loaded '{fp}'")


def get(key: str, default=None):
    return _CONFIG.get(key, default)


def get_str(key: str, default=""):
    try:
        return str(_CONFIG[key])
    except ValueError:
        return default


def get_bool(key: str, default=False):
    try:
        return bool(_CONFIG[key])
    except ValueError:
        return default


def get_int(key: str, default=0):
    try:
        return int(_CONFIG[key])
    except ValueError:
        return default
