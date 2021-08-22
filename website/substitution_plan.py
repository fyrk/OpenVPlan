#  GaW-Vertretungsplan
#  Copyright (C) 2019-2021  Florian Rädiker
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU Affero General Public License as published
#  by the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU Affero General Public License for more details.
#
#  You should have received a copy of the GNU Affero General Public License
#  along with this program.  If not, see <https://www.gnu.org/licenses/>.

import asyncio
import datetime
import json
import logging
import sqlite3
import time
from _weakrefset import WeakSet
from email.utils import formatdate
from typing import Iterable, MutableSet, Optional, Tuple, Callable, Awaitable
from urllib.parse import urlparse

import pywebpush
import yarl
from aiohttp import ClientSession, web, WSMessage, WSMsgType
from aiojobs.aiohttp import get_scheduler

from settings import settings
from subs_crawler.crawlers.base import BaseSubstitutionCrawler
from subs_crawler.utils import split_selection
from website import logger
from website.db import SubstitutionPlanDB, hash_endpoint

_LOGGER = logging.getLogger("gawvertretung")

# Time when a "<plan-name>-selection" cookie expires. This is on 29th July, as on this date, summer holidays in Lower
# Saxony normally take place.
# Starting at 14h June, the cookie is set until the next year.
now = datetime.datetime.now()
SELECTION_COOKIE_EXPIRE = formatdate(time.mktime(
    datetime.datetime(now.year if now < datetime.datetime(now.year, 6, 14) else now.year + 1, 7, 29).timetuple()))
# Time for a cookie which should be deleted (Thu, 01 Jan 1970 00:00:00 GMT)
DELETE_COOKIE_EXPIRE = formatdate(0)


csp = {
    "default-src": "'none'",
    "style-src": "'self'",
    "manifest-src": "'self'",
    "img-src": "'self' data:",
    "script-src": [
        "'self'",
        "'sha256-VXAFuXMdnSA19vGcFOCPVOnWUq6Dq5vRnaGtNp0nH8g='",  # const a=localStorage.getItem("dark-theme") ...
        "'sha256-3/1ODIQTRjv+w06gdm2GcdfvbXBk8D893PBaImH3siQ='",  # document.getElementById("view-e") ...
        "'sha256-DxdO0KMifr4qBxX++GTv0w7cNu8FeArRvitEZf1FSrE='",  # window.plausible=window.plausible||function() ...
        "'sha256-bfloDFhW9eAYHv7CGM+kIiD7H2F+b/hGF5Wj8LOnLyo='",  # plausible("404",{props:{path:document.location ...
        "'sha256-MUo3BR9SqVxUnxV7Dw9uvwDu81yLUU2qKuLSqkGuXmE='",  # plausible("500",{props:{path:document.location ...
    ],
    "connect-src": ["'self'", "ws:" if settings.DEBUG else "wss:"],
    "frame-src": "'self' mailto:",
    "object-src": "'self' mailto:"
}
if settings.PLAUSIBLE and (plausible_js := settings.PLAUSIBLE.get("js")):
    csp["script-src"].append(plausible_js)
if settings.PLAUSIBLE and (plausible_endpoint := settings.PLAUSIBLE.get("endpoint")):
    csp["connect-src"].append(plausible_endpoint)
for name, value in settings.ADDITIONAL_CSP_DIRECTIVES.items():
    if type(csp[name]) is not list:
        csp[name] = [csp[name]]
    if type(value) is not list:
        value = [value]
    csp[name].extend(value)

csp_header = ""
for key, value in csp.items():
    if type(value) is list:
        value = " ".join(value)
    csp_header += key + " " + value + "; "

RESPONSE_HEADERS = {
    "Content-Security-Policy": csp_header,
    "Strict-Transport-Security": "max-age=63072000",
    "Referrer-Policy": "same-origin",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1",
    "X-Robots-Tag": "noarchive, notranslate"
}
if settings.HEADERS_BLOCK_FLOC:
    RESPONSE_HEADERS["Permissions-Policy"] = "interest-cohort=()"

RESPONSE_HEADERS_SELECTION = {
    **RESPONSE_HEADERS,
    "X-Robots-Tag": "noindex"
}

# intercept pywebpush.WebPusher.as_curl() call in pywebpush.WebPusher.send() so that request can be made with aiohttp
# a call to pywebpush.webpush will now return (endpoint, data, headers)
pywebpush.WebPusher.as_curl = lambda s, e, d, h: (e, d, h)


class SubstitutionPlan:
    def __init__(self, plan_id: str, crawler: BaseSubstitutionCrawler, render_func: Callable[..., Awaitable[str]]):
        self._plan_id = plan_id
        self._crawler = crawler
        self._render_func = render_func

        self._index_site = None
        self._serialization_filepath = None
        self._db: Optional[SubstitutionPlanDB] = None
        self._client_session: Optional[ClientSession] = None
        self._app: Optional[web.Application] = None
        self._websockets: MutableSet[web.WebSocketResponse] = WeakSet()

    def set_db(self, db: SubstitutionPlanDB):
        if self._db is not None:
            raise ValueError("db already set")
        self._db = db
        self._crawler.last_version_id = self._db.get_substitutions_version_id(self._plan_id)
        logger.PLAN_NAME_CONTEXTVAR.set(self._plan_id)
        _LOGGER.debug(f"Last substitution version id is: {self._crawler.last_version_id!r}")
        logger.PLAN_NAME_CONTEXTVAR.set(None)

    def set_client_session(self, client_session: ClientSession):
        if self._client_session is not None:
            raise ValueError("client_session already set")
        self._client_session = client_session

    def create_app(self, static_path: Optional[str] = None) -> web.Application:
        self._app = web.Application()
        self._app.add_routes([
            web.get("/", self._root_handler),
            web.get("/api/wait-for-updates", self._wait_for_updates_handler),
            web.post("/api/subscribe-push", self._subscribe_push_handler)
        ])
        if static_path:
            self._app.router.add_static("/", static_path)
        return self._app

    async def close(self):
        for ws in self._websockets:
            await ws.close()
        self._websockets.clear()

    @staticmethod
    def parse_selection(url: yarl.URL) -> Tuple[str, str, str]:
        selection = ""
        selection_str = ""
        selection_qs = ""
        if "s" in url.query:
            selection_qs = ",".join(url.query.getall("s"))
            selection = split_selection(selection_qs)
            if selection:
                selection_str = ", ".join(selection)
                selection = [s.upper() for s in selection]
        return selection, selection_str, selection_qs

    @logger.plan_name_wrapper
    async def update_substitutions(self, scheduler, fake_affected_groups=None):
        _LOGGER.info("Updating substitutions...")
        if fake_affected_groups:
            changed = True
            affected_groups = fake_affected_groups
        else:
            changed, affected_groups = await self._crawler.update(self._client_session)
        if changed:
            _LOGGER.info("Substitutions have changed")
            self._index_site = await self._render_func(storage=self._crawler.storage)
            await scheduler.spawn(self._on_new_substitutions(affected_groups))
        elif settings.DEBUG:
            self._index_site = await self._render_func(storage=self._crawler.storage)

    # ===================
    # REQUEST HANDLERS

    # /
    @logger.plan_name_wrapper
    async def _root_handler(self, request: web.Request) -> web.Response:
        # noinspection PyBroadException
        try:
            if "all" not in request.query and "s" not in request.query:
                # "<plan-id>-selection" is the name of the cookie previously used to store the selection
                selection = None
                if "selection" in request.cookies and (s := request.cookies["selection"].strip()):
                    selection = s
                elif self._plan_id + "-selection" in request.cookies \
                        and (s := request.cookies[self._plan_id + "-selection"].strip()):
                    selection = s
                # use 'update_query' so that existing query doesn't change for e.g. "mtm_campaign" to work
                if selection is not None:
                    raise web.HTTPSeeOther(location=request.rel_url.update_query(s=selection))
                else:
                    raise web.HTTPSeeOther(location=request.rel_url.update_query("all"))

            fake_affected_groups = None
            if settings.DEBUG:
                if "raise500" in request.query:
                    raise ValueError
                if "event" in request.query:
                    # in development, simulate new substitutions event by "event" parameter
                    fake_affected_groups = json.loads(request.query["event"])

            await self.update_substitutions(get_scheduler(request), fake_affected_groups)

            selection, selection_str, selection_qs = self.parse_selection(request.url)

            if not selection:
                text = self._index_site
                headers = RESPONSE_HEADERS
            else:
                text = await self._render_func(storage=self._crawler.storage,
                                               selection=selection, selection_str=selection_str)
                headers = RESPONSE_HEADERS_SELECTION

            response = web.Response(text=text, content_type="text/html", charset="utf-8",
                                    headers=headers)
            if request.cookies.get("selection", "").strip() != selection_qs:
                # appropriate cookie is missing, set it
                response.set_cookie("selection", selection_qs,
                                    expires=SELECTION_COOKIE_EXPIRE, path="/" + self._plan_id + "/",
                                    secure=not settings.DEBUG,  # secure in non-development mode
                                    httponly=True, samesite="Lax")
            await response.prepare(request)
            await response.write_eof()
        except web.HTTPException:
            raise
        except Exception:
            _LOGGER.exception("Exception while handling substitution request")
            # set info for error handling in server.py
            request["plan_id"] = self._plan_id
            raise
        return response

    # /api/wait-for-updates
    @logger.plan_name_wrapper
    async def _wait_for_updates_handler(self, request: web.Request):
        ws = web.WebSocketResponse()
        if not ws.can_prepare(request):
            raise web.HTTPNotFound()
        await ws.prepare(request)

        self._websockets.add(ws)
        try:
            msg: WSMessage
            async for msg in ws:
                _LOGGER.debug("WebSocket: Got message " + str(msg))
                if msg.type in (WSMsgType.CLOSE, WSMsgType.ERROR):
                    return
                elif msg.type == WSMsgType.TEXT:
                    try:
                        data = msg.json()
                    except json.JSONDecodeError:
                        _LOGGER.exception("WebSocket: Received malformed JSON message")
                    else:
                        if "type" in data:
                            if data["type"] == "get_status":
                                await self.update_substitutions(get_scheduler(request))
                                await ws.send_json({"type": "status", "status": self._crawler.storage.status})
            # no need to remove ws from self._websockets as self._websockets is a WeakSet
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass
        finally:
            _LOGGER.info(f"WebSocket connection closed: {ws.close_code}")
        return ws

    # /api/subscribe-push
    @logger.plan_name_wrapper
    async def _subscribe_push_handler(self, request: web.Request):
        # noinspection PyBroadException
        try:
            data = await request.json()
            if data["is_active"]:
                self._db.add_push_subscription(self._plan_id, data["subscription"], data["selection"])
                #if not await self.send_push_notification(data["subscription"], {
                #    "type": "generic_message",
                #    "title": "Benachrichtigungen erfolgreich aktiviert!",
                #    "body": "GaW Vertretungsplan"
                #}):
                #    raise ValueError("Could not send push notification to newly subscribed endpoint")
            else:
                self._db.delete_push_subscription(self._plan_id, data["subscription"]["endpoint"])
            self._db.commit()
            response = web.json_response({"ok": True})
        except Exception:
            _LOGGER.exception("Modifying push subscription failed")
            response = web.json_response({"ok": False}, status=400)
        return response

    async def send_push_notification(self, subscription: dict, data) -> bool:
        endpoint_hash = hash_endpoint(subscription["endpoint"])
        # noinspection PyBroadException
        try:
            url = urlparse(subscription.get("endpoint"))  # copied from pywebpush.webpush
            aud = "{}://{}".format(url.scheme, url.netloc)

            _LOGGER.debug(f"Sending push notification to {self._plan_id}-{endpoint_hash[:6]} ({aud})")

            endpoint, data, headers = pywebpush.webpush(
                subscription, json.dumps(data),
                vapid_private_key=settings.PRIVATE_VAPID_KEY,
                vapid_claims={
                    "sub": settings.VAPID_SUB,
                    # "aud": endpoint_origin,  # aud is automatically set in webpush()
                    # 86400s=24h, but 5s less because otherwise, requests sometimes fail (exp must not
                    # be longer than 24 hours from the time the request is made)
                    "exp": int(time.time()) + 86395,
                    "aud": aud
                },
                content_encoding=settings.WEBPUSH_CONTENT_ENCODING,
                ttl=86400,
                curl=True)  # modifications to make this work: see beginning of this file
            async with self._client_session.post(endpoint, data=data, headers=headers) as r:
                if r.status >= 400:
                    # If status code is 404 or 410, the endpoints are unavailable, so delete the
                    # subscription. See https://autopush.readthedocs.io/en/latest/http.html#error-codes.
                    if r.status in (404, 410):
                        _LOGGER.debug(f"No longer valid subscription {self._plan_id}-{endpoint_hash[:6]} ({aud}): "
                                      f"{r.status} {r.reason} {repr(await r.text())}")
                        return False
                    else:
                        _LOGGER.error(
                            f"Could not send push notification to {self._plan_id}-{endpoint_hash[:6]} ({aud}): "
                            f"{r.status} {r.reason} {repr(await r.text())}")
                else:
                    _LOGGER.debug(f"Successfully sent push notification to {self._plan_id}-{endpoint_hash[:6]}: "
                                  f"{r.status} {r.reason} {repr(await r.text())}")
        except Exception:
            _LOGGER.exception(f"Could not send push notification to {self._plan_id}-{endpoint_hash[:6]}")
        return True

    # background task on new substitutions
    async def _on_new_substitutions(self, affected_groups):
        logger.REQUEST_ID_CONTEXTVAR.set(None)
        # noinspection PyBroadException
        try:
            self._db.set_substitutions_version_id(self._plan_id, self._crawler.last_version_id)
            _LOGGER.debug(f"Changed last substitution version id to: {self._crawler.last_version_id!r}")

            # WEBSOCKETS
            _LOGGER.debug(f"Sending update event via WebSocket connection to {len(self._websockets)} clients")
            for ws in self._websockets:
                try:
                    await ws.send_json({"type": "status", "status": self._crawler.storage.status})
                except:
                    pass

            # PUSH NOTIFICATIONS
            if affected_groups:
                _LOGGER.debug("Sending affected groups via push messages")

                def iter_relevant_subscriptions():
                    row: sqlite3.Row
                    for row in self._db.iter_push_subscriptions(self._plan_id):
                        selection = row["selection"]
                        if selection is None:
                            # selection is None when all groups are selected
                            yield row["subscription"], affected_groups
                        else:
                            intersection = {}
                            for expiry_time, day in affected_groups.items():
                                groups = day["groups"]
                                common_groups = [s for s in selection if any(s in g for g in groups)]
                                if common_groups:
                                    intersection[expiry_time] = {"name": day["name"], "groups": common_groups}
                            if intersection:
                                yield row["subscription"], intersection

                timestamp = self._crawler.storage.status_datetime.timestamp()

                async def send_notification(subscription, common_affected_groups):
                    data = {
                        "type": "subs_update",
                        "affected_groups_by_day": common_affected_groups,
                        "plan_id": self._plan_id,
                        # status_datetime.timestamp() correctly assumes that datetime is local
                        # time (status_datetime has no tzinfo) and returns the correct UTC
                        # timestamp
                        "timestamp": timestamp
                    }
                    if not await self.send_push_notification(subscription, data):
                        return subscription["endpoint"]

                endpoints_to_delete: Iterable[Optional[str]] = await asyncio.gather(
                    *(send_notification(s, c) for s, c in iter_relevant_subscriptions()))
                for endpoint in endpoints_to_delete:
                    if endpoint is not None:
                        self._db.delete_push_subscription(self._plan_id, endpoint)
                self._db.commit()
        except Exception:
            _LOGGER.exception("Exception in on_new_substitutions background task")
