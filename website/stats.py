import datetime
import json
import os.path
from collections import Counter


class Stats:
    _DATA_BASE = {"statuses": [], "last-sites": [], "requests": {}, "bot_requests": [], "requests_not_found": {},
                  "requests_method_not_allowed": {}}
    _BOT_USER_AGENTS = ["bot",     # GoogleBots,  Bingbot, DuckDuckBot, YandexBot, Exabot, Facebot
                        "spider",  # Baiduspider, Sogou Spider
                        "crawl",   # ia_archiver (Alexa)
                        "yahoo",   # Slurp (Yahoo)
                        "google"   # Google Image Proxy 11
                        ]

    def __init__(self, filename):
        if os.path.exists(filename):
            self.data = self._DATA_BASE
            try:
                with open(filename, "r") as f:
                    self.data.update(json.load(f))
            except json.JSONDecodeError:
                pass
            self.data["requests"] = {time: {user_agent: Counter(paths) for user_agent, paths in time_data.items()}
                                     for time, time_data in self.data["requests"].items()}
        else:
            self.data = self._DATA_BASE
        self.filename = filename
        self.status_was_new = False

    def add_status(self, status):
        if status not in self.data["statuses"]:
            self.data["statuses"].append(status)
            self.status_was_new = True
        else:
            self.status_was_new = False

    def new_request(self, path, user_agent):
        user_agent_lower = user_agent.lower()
        if any(agent in user_agent_lower for agent in self._BOT_USER_AGENTS):
            time = datetime.datetime.now().strftime("%Y-%m-%d %X")
            self.data["bot_requests"].append([time, path, user_agent])
        else:
            time = datetime.datetime.now().strftime("%Y-%m-%d")
            if time not in self.data["requests"]:
                self.data["requests"][time] = {}
            if user_agent not in self.data["requests"][time]:
                self.data["requests"][time][user_agent] = Counter()
            self.data["requests"][time][user_agent][path] += 1

    def _new_bad_request(self, environ, type_):
        time = datetime.datetime.now().strftime("%Y-%m-%d %X")
        environ_str = str(environ)
        if environ["PATH_INFO"] not in self.data[type_]:
            self.data[type_][environ["PATH_INFO"]] = {time: environ_str}
        else:
            self.data[type_][environ["PATH_INFO"]][time] = environ_str

    def new_not_found(self, environ):
        self._new_bad_request(environ, "requests_not_found")

    def new_method_not_allowed(self, environ):
        self._new_bad_request(environ, "requests_method_not_allowed")

    def add_last_site(self, site_num):
        if self.status_was_new:
            self.data["last-sites"].append(site_num)

    def save(self):
        with open(self.filename, "w") as f:
            json.dump(self.data, f, indent=4)
