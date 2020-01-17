import datetime
import hashlib
import json
import os.path


class Stats:
    _BOT_USER_AGENTS = [
        "bot",     # GoogleBots, Bingbot, DuckDuckBot, YandexBot, Exabot, Facebot
        "spider",  # Baiduspider, Sogou Spider
        "crawl",   # ia_archiver (Alexa)
        "yahoo",   # Slurp (Yahoo)
        "google"   # Google Image Proxy 11
    ]

    def __init__(self, stats_dir):
        self._directory = stats_dir

        def from_json_data(path, base_data):
            if os.path.exists(path):
                try:
                    with open(path, "r", encoding="utf-8") as f:
                        base_data.update(json.load(f))
                except json.JSONDecodeError:
                    pass
            return base_data

        # STATUSES
        self._path_statuses_data = os.path.join(self._directory, "statuses.json")
        self._statuses_data = from_json_data(self._path_statuses_data, {"statuses": []})

        # USER REQUESTS
        self._path_requests_data = os.path.join(self._directory, "requests.json")
        self._requests_data = from_json_data(self._path_requests_data, {"users": {}})

        # BAD REQUESTS
        self._bad_requests_file = os.path.join(self._directory, "bad_requests.txt")

        # BOT REQUESTS
        self._bot_requests_file = os.path.join(self._directory, "bot_requests.txt")

    def save(self):
        def save_json(path, data):
            with open(path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)

        save_json(self._path_statuses_data, self._statuses_data)
        save_json(self._path_requests_data, self._requests_data)

    def add_status(self, status):
        self._statuses_data["statuses"].append([status])

    def add_last_site(self, site_num):
        if len(self._statuses_data["statuses"][-1]) == 1:
            self._statuses_data["statuses"][-1].append(site_num)

    def _get_ip(self, environ):
        ip_address = environ.get("REMOTE_ADDR")
        if not ip_address:
            ip_address = environ.get("HTTP_X_FORWARDED_FOR")
        return ip_address, (hashlib.sha256(ip_address.encode("utf-8")).hexdigest()[:12] if ip_address else "unknown")

    def new_request(self, environ):
        ip_address, ip_hash = self._get_ip(environ)
        if ip_hash != "edbd6af54a1c":  # hash for own web server, curl is ignored
            path = environ["REQUEST_METHOD"][0] + environ["PATH_INFO"]
            referer = environ.get("HTTP_REFERER")
            user_agent = environ.get("HTTP_USER_AGENT", "unknown")
            user_agent_lower = user_agent.lower()
            time = datetime.datetime.now().strftime("%Y-%m-%d %X")
            if any(agent in user_agent_lower for agent in self._BOT_USER_AGENTS):
                text = time + " " + path + " " + ip_address + " " + user_agent
                if referer:
                    text += ", Referer: " + referer
                with open(self._bot_requests_file, "a", encoding="utf-8") as f:
                    f.write(text + "\n")
            else:
                if ip_hash not in self._requests_data["users"]:
                    self._requests_data["users"][ip_hash] = {}
                if user_agent not in self._requests_data["users"][ip_hash]:
                    self._requests_data["users"][ip_hash][user_agent] = []
                text = time + " " + path
                if referer:
                    text += ", Referer: " + referer
                self._requests_data["users"][ip_hash][user_agent].append(text)

    def _new_bad_request(self, environ, type_):
        _, ip_hash = self._get_ip(environ)
        path = environ["REQUEST_METHOD"][0] + environ["PATH_INFO"]
        user_agent = environ.get("HTTP_USER_AGENT", "unknown")
        referer = environ.get("HTTP_REFERER")
        time = datetime.datetime.now().strftime("%Y-%m-%d %X")
        text = type_ + " " + time + " " + path + " " + ip_hash + " " + user_agent
        if referer:
            text += ", Referer: " + referer
        with open(self._bad_requests_file, "a", encoding="utf-8") as f:
            f.write(text + "\n")

    def new_not_found(self, environ):
        self._new_bad_request(environ, "NOT FOUND")

    def new_method_not_allowed(self, environ):
        self._new_bad_request(environ, "METHOD NOT ALLOWED")
