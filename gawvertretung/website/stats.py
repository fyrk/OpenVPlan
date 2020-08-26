import csv
import datetime
import hashlib
import logging
import os.path

from aiohttp import web, hdrs

from .. import config

_LOGGER = logging.getLogger("gawvertretung")


class Stats:
    _BOT_USER_AGENTS = [
        "bot",    # Google Bots, Bingbot, DuckDuckBot, YandexBot, Exabot, Facebot
        "spider", # Baiduspider, Sogou Spider
        "crawl",  # ia_archiver (Alexa)
        "yahoo",  # Slurp (Yahoo)
        "google"  # Google Image Proxy 11
    ]

    def __init__(self, directory):
        self._last_sites = csv.writer(open(os.path.join(directory, "statuses.csv"), "a", newline=""))
        self._requests = csv.writer(open(os.path.join(directory, "requests.csv"), "a", newline=""))

    async def add_last_site(self, plan_name: str, status: str, last_site: int):
        self._last_sites.writerow((plan_name, status, last_site))

    async def new_request(self, request: web.Request, response: web.Response, time):
        remote = request.remote if not config.get_bool("is_proxied") else request.headers.get("X-Real-IP")
        if response.status >= 400:
            type_ = "BAD"
        else:
            user_agent_lower = request.headers.get(hdrs.USER_AGENT).lower()
            if any(agent in user_agent_lower for agent in self._BOT_USER_AGENTS):
                type_ = "BOT"
            else:
                type_ = "ALL"
                remote = hashlib.blake2b(remote.encode("utf-8"), digest_size=3).hexdigest()
        self._requests.writerow((type_, datetime.datetime.now().strftime("%Y-%m-%d %X"),
                                 response.status, response.reason, request.method,
                                 request.path, time, response.body_length,
                                 request.headers.get(hdrs.USER_AGENT), request.headers.get(hdrs.REFERER), remote))
