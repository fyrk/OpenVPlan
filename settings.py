from typing import Optional, Dict, Any

from aiohttp import http, hdrs


class settings:
    VERSION = "5.0"

    HOST = "localhost"
    PORT = 8080

    DEBUG = False

    LOGFILE = "logs/website.log"
    DATA_DIR = "data/"

    IS_PROXIED = False

    TEMPLATE_404: str = "error-404.min.html"
    TEMPLATE_500: str = "error-500-all.min.html"

    PUBLIC_VAPID_KEY: Optional[str] = None
    PRIVATE_VAPID_KEY: Optional[str] = None
    VAPID_SUB: Optional[str] = None

    MATOMO_URL: Optional[str] = None
    MATOMO_SITE_ID: Optional[str] = None
    MATOMO_AUTH_TOKEN: Optional[str] = None
    MATOMO_TRACK_BOTS = False

    MATOMO_HEADERS: Optional[dict] = None
    MATOMO_HONOR_DNT: bool = True

    REQUEST_HEADERS: dict = {
        hdrs.USER_AGENT: f"Mozilla/5.0 (compatible; GaWVertretungBot/{VERSION}; "
                         f"+https://gawvertretung.florian-raediker.de) {http.SERVER_SOFTWARE}"
    }

    HEADERS_BLOCK_FLOC = True

    DEFAULT_PLAN_ID: Optional[str] = None

    SUBSTITUTION_PLANS: Optional[Dict[str, Dict[str, Dict[str, Any]]]] = None

    __locked = False

    def __setattr__(self, key, value):
        if self.__locked:
            raise AttributeError("Can't change setting")
        else:
            super().__setattr__(key, value)


try:
    import local_settings
except ImportError:
    pass
settings.__locked = True

settings = settings()
