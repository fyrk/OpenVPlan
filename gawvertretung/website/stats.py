import datetime
import logging
import os.path

from aiohttp import web, hdrs

_LOGGER = logging.getLogger("gawvertretung")


class Stats:
    _BOT_USER_AGENTS = [
        "bot",  # GoogleBots, Bingbot, DuckDuckBot, YandexBot, Exabot, Facebot
        "spider",  # Baiduspider, Sogou Spider
        "crawl",  # ia_archiver (Alexa)
        "yahoo",  # Slurp (Yahoo)
        "google"  # Google Image Proxy 11
    ]

    def __init__(self, stats_dir):
        self._directory = stats_dir

        self._path_last_sites = os.path.join(self._directory, "statuses.txt")
        self._path_requests = os.path.join(self._directory, "requests.txt")
        self._path_bad_requests = os.path.join(self._directory, "bad_requests.txt")
        self._path_bot_requests = os.path.join(self._directory, "bot_requests.txt")

    @staticmethod
    async def _add_to_file(path, text):
        with open(path, "a", encoding="utf-8") as f:
            f.write(text)

    async def add_last_site(self, plan_name: str, status: str, last_site: int):
        await self._add_to_file(self._path_last_sites, plan_name + " " + status + " " + str(last_site) + "\n")

    async def new_request(self, request: web.Request, response: web.Response):
        if response.status >= 400:
            return await self.new_bad_request(request, response)
        if request.remote != request.host:
            user_agent = request.headers[hdrs.USER_AGENT]
            user_agent_lower = user_agent.lower()
            t = datetime.datetime.now().strftime("%Y-%m-%d %X")
            if referer := request.headers.get(hdrs.REFERER):
                referer = ' Referer:"' + referer + '"'
            else:
                referer = ""
            if any(agent in user_agent_lower for agent in self._BOT_USER_AGENTS):
                await self._add_to_file(self._path_bot_requests, t + " " + request.method + " " + request.path + " " +
                                        request.remote + " " + user_agent + referer + "\n")
            else:
                await self._add_to_file(self._path_requests, t + " " + request.method + " " + request.path + " " +
                                        " " + user_agent + referer + "\n")

    async def new_bad_request(self, request: web.Request, response: web.Response):
        with open(self._path_bad_requests, "a", encoding="utf-8") as f:
            f.write(str(response.status) + " " + response.reason + " " + request.method + " " + request.path + " " +
                    request.remote + "\n")
