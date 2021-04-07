import csv
import datetime
import logging
from typing import Optional, overload, Union

import yarl
from aiohttp import hdrs, web, ClientSession

from settings import settings
from subs_crawler.utils import split_class_name
from website.substitution_plan import SubstitutionPlan

_LOGGER = logging.getLogger("gawvertretung")


class Stats:
    def __init__(self, status_filepath, matomo_url, matomo_site_id, matomo_auth_token, respect_dnt, headers=None):
        self.status_file = open(status_filepath, "a", newline="", buffering=1)
        self.status = csv.writer(self.status_file)

        self.client_session: Optional[ClientSession] = None
        self.matomo_url = matomo_url
        self.matomo_site_id = matomo_site_id
        self.matomo_auth_token = matomo_auth_token
        self.respect_dnt = respect_dnt
        self.headers = headers

    def __del__(self):
        self.status_file.close()

    async def add_last_site(self, plan_name: str, status: str, last_site: int):
        self.status.writerow((plan_name, status, last_site))

    async def _check_dnt(self, request: web.Request):
        if settings.MATOMO_HONOR_DNT and request.headers.get("DNT", "0") == "1":
            params = {
                "idsite": self.matomo_site_id,
                "rec": "1",
                "apiv": "1",
                "send_image": "0",
                "ua": "",
                "action_name": "Do Not Track enabled",
            }
            if self.matomo_auth_token:
                params["token_auth"] = self.matomo_auth_token
                # without this, Matomo thinks the originating IP address of the request is the server's IP
                # "" doesn't work, so use "::1" instead
                params["cip"] = "::1"
            async with self.client_session.get(self.matomo_url, params=params, headers=self.headers) as r:
                _LOGGER.debug(f"Sent info to Matomo (DNT): {r.request_info.url} {r.status} '{await r.text()}'")
            return True
        return False

    @overload
    async def _send_to_matomo(self, request: web.Request, time=None,
                              action_name=None,
                              url=None,
                              urlref=None,
                              ca=False,
                              #dimensions,
                              e_c=None,
                              e_a=None,
                              e_n=None,
                              e_v=None,
                              ):
        ...

    async def _send_to_matomo(self, request: web.Request, **kwargs):
        # noinspection PyBroadException
        try:
            now = datetime.datetime.now()
            params = {
                "idsite": self.matomo_site_id,
                "rec": "1",
                "apiv": "1",

                "bots": 1 if settings.MATOMO_TRACK_BOTS else 0,
                "send_image": "0",
                "h": now.hour,
                "m": now.minute,
                "s": now.second,
                "ua": request.headers.get(hdrs.USER_AGENT, ""),
                "lang": request.headers.get(hdrs.ACCEPT_LANGUAGE, ""),
            }
            if kwargs.get("time"):
                params["gt_ms"] = str(int(round(int(kwargs["time"]) * 0.000001)))
            if kwargs.get("ca"):
                kwargs["ca"] = "1"
            params.update(kwargs)
            if self.matomo_auth_token:
                params["token_auth"] = self.matomo_auth_token
                params["cip"] = request.remote if not settings.IS_PROXIED else request.headers.get("X-Real-IP")
            if "matomo_ignore" in request.cookies:
                cookies = {"matomo_ignore": request.cookies["matomo_ignore"]}
            else:
                cookies = None
            async with self.client_session.get(self.matomo_url, params=params, headers=self.headers,
                                               cookies=cookies) as r:
                _LOGGER.debug(f"Sent info to Matomo: {r.status} '{await r.text()}'")
        except Exception:
            _LOGGER.exception("Exception while sending tracking information to Matomo")

    @staticmethod
    def anonymize_url(url: Union[str, yarl.URL]) -> str:
        def anonymize_selection(s: str):
            digits, letters = split_class_name(s)
            if not digits:
                return "xxx"
            return digits + "x"*len(letters)
        url = yarl.URL(url)
        selection, _, _ = SubstitutionPlan.parse_selection(url)
        if selection:
            url %= {"s": ",".join(anonymize_selection(s) for s in selection)}
        return str(url)

    async def track_page_view(self, request: web.Request, is_sw, time, title):
        if await self._check_dnt(request):
            return
        if not is_sw:
            await self._send_to_matomo(
                request,
                time=time,
                action_name=title,
                url=self.anonymize_url(request.url),
                urlref=self.anonymize_url(request.headers.get(hdrs.REFERER, "")),
            )
        else:
            url = self.anonymize_url(request.url)
            await self._send_to_matomo(
                request,
                time=time,
                url=url,
                urlref=self.anonymize_url(request.headers.get(hdrs.REFERER, "")),
                e_c="Service Worker Request",
                e_a=url,
                ca=True
            )

    async def track_push_subscription(self, request: web.Request, time, plan_name, is_active):
        if await self._check_dnt(request):
            return
        if is_active is None:
            action = "None"
        elif is_active:
            action = "Subscribe"
        else:
            action = "Unsubscribe"
        await self._send_to_matomo(
            request,
            time=time,
            #action_name=f"API / {plan_name} / {action} Push",
            url=self.anonymize_url(request.headers.get(hdrs.REFERER, "")),
            e_c="Push Subscription",
            e_n=plan_name,
            e_a=action,
            ca=True
        )

    async def track_4xx_error(self, request: web.Request, time, response: web.Response):
        url = self.anonymize_url(request.url)
        action_name = f"{response.status} {response.reason}/URL = {url}"
        if hdrs.REFERER in request.headers:
            action_name += "/From = " + self.anonymize_url(request.headers[hdrs.REFERER])
        await self._send_to_matomo(
            request,
            time=time,
            action_name=action_name,
            url=url
        )

    async def track_js_error(self, request, name, message, description, number, filename, lineno, colno, stack):
        await self._send_to_matomo(
            request,
            #action_name=f"API / Report JS Error",
            url=self.anonymize_url(request.headers.get(hdrs.REFERER, "")),
            e_c="JavaScript Errors",
            e_n=f"{name} {message}",
            e_a=f"{stack} {filename}:{lineno}:{colno}, {description}, {number}",
            ca=True
        )
