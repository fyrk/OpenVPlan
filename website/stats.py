import csv
import datetime
import hashlib
import json
import logging
import os.path

from aiohttp import hdrs, web

from website import config

_LOGGER = logging.getLogger("gawvertretung")


class Stats:
    _BOT_USER_AGENTS = [
        "bot",    # Google Bots, Bingbot, DuckDuckBot, YandexBot, Exabot, Facebot
        "spider", # Baiduspider, Sogou Spider
        "crawl",  # ia_archiver (Alexa)
        "yahoo",  # Slurp (Yahoo)
        "google"  # Google Image Proxy 11
    ]

    def __init__(self, directory, known_js_errors_filepath):
        with open(known_js_errors_filepath, "r") as f:
            self.known_js_errors = {k: v if type(v) == list else [v] for k, v in json.load(f).items()}
        self._status_file = open(os.path.join(directory, "status.csv"), "a", newline="", buffering=1)
        self._status = csv.writer(self._status_file)
        self._requests_file = open(os.path.join(directory, "requests.csv"), "a", newline="", buffering=1)
        self._requests = csv.writer(self._requests_file)
        self._js_errors_file = open(os.path.join(directory, "js_errors.csv"), "a", newline="", buffering=1)
        self._js_errors = csv.writer(self._js_errors_file)
        self._known_js_errors_file = open(os.path.join(directory, "known_js_errors.csv"), "a", newline="", buffering=1)
        self._known_js_errors = csv.writer(self._known_js_errors_file)

    def __del__(self):
        self._status_file.close()
        self._requests_file.close()
        self._js_errors_file.close()

    async def add_last_site(self, plan_name: str, status: str, last_site: int):
        self._status.writerow((plan_name, status, last_site))

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
                if config.get_bool("log_ip_address"):
                    remote = hashlib.blake2b(remote[1:-2].encode("utf-8"), digest_size=3).hexdigest()
                else:
                    remote = ""
        self._requests.writerow((type_, datetime.datetime.now().strftime("%Y-%m-%d %X"),
                                 response.status, response.reason, request.method,
                                 request.path_qs, time, response.body_length,
                                 request.headers.get(hdrs.USER_AGENT), request.headers.get(hdrs.REFERER), remote))

    async def new_js_error(self, name, message, description, number, filename, lineno, colno, stack, user_agent):
        # find out whether error is new or already known
        is_known = False
        if name in self.known_js_errors:
            reported = dict(name=name, message=message, description=description, number=number, filename=filename,
                            lineno=lineno, colno=colno, stack=stack, user_agent=user_agent)
            for error in self.known_js_errors[name]:
                for key, value in error.items():
                    if key.endswith("*"):
                        key = key[:-1]
                        if not (key in reported and value in reported[key]):
                            break
                    else:
                        if reported[key] != value:
                            break
                else:
                    # loop did not break, reported error matches known error
                    is_known = True
                    break

        (self._known_js_errors if is_known else self._js_errors).writerow(
            (datetime.datetime.now().isoformat(), name, message, description, number,
             filename, lineno, colno, stack, user_agent))
