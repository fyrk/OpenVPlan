import asyncio
import datetime
import json
import logging
import sqlite3
import time
from _weakrefset import WeakSet
from email.utils import formatdate
from typing import Dict, Iterable, List, MutableSet, Optional, Union, Tuple, Callable

import jinja2
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
now = datetime.datetime.now()
SELECTION_COOKIE_EXPIRE = formatdate(time.mktime(
    datetime.datetime(now.year if now < datetime.datetime(now.year, 7, 29) else now.year + 1, 7, 29).timetuple()))
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
if plausible_js := settings.TEMPLATE_OPTIONS.get("plausible_js"):
    csp["script-src"].append(plausible_js)
if plausible_endpoint := settings.TEMPLATE_OPTIONS.get("plausible_endpoint"):
    csp["connect-src"].append(plausible_endpoint)

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
    def __init__(self, plan_id: str, crawler: BaseSubstitutionCrawler, template: Callable[[], jinja2.Template],
                 error500_template: Callable[[], jinja2.Template], template_options: dict, uppercase_selection: bool):
        self._plan_id = plan_id
        self._crawler = crawler
        self._template = template
        self._error500_template = error500_template
        self._template_options = template_options
        self._template_options["id"] = self._plan_id
        self._uppercase_selection = uppercase_selection

        self._index_site = None
        self._serialization_filepath = None
        self._db: Optional[SubstitutionPlanDB] = None
        self._client_session: Optional[ClientSession] = None
        self._app: Optional[web.Application] = None
        self._websockets: MutableSet[web.WebSocketResponse] = WeakSet()
        # affected groups are passed from self._root_handler to self._background_tasks:
        self._affected_groups: Optional[Dict[int, Dict[str, Union[str, List[str]]]]] = None

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

    async def _recreate_index_site(self):
        self._index_site = await self._template().render_async(storage=self._crawler.storage,
                                                               options=self._template_options)

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

    # ===================
    # REQUEST HANDLERS

    # /
    @logger.request_wrapper
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

            substitutions_have_changed, affected_groups = await self._crawler.update(self._client_session)
            if settings.DEBUG and "raise500" in request.query:
                raise ValueError
            if settings.DEBUG and "event" in request.query:
                # in development, simulate new substitutions event by "event" parameter
                substitutions_have_changed = True
                affected_groups = json.loads(request.query["event"])
            if substitutions_have_changed:
                _LOGGER.info("SUBSTITUTIONS HAVE CHANGED")
                self._affected_groups = affected_groups

            selection, selection_str, selection_qs = self.parse_selection(request.url)
            if self._uppercase_selection:
                selection_str = selection_str.upper()

            if not selection:
                if substitutions_have_changed or not self._index_site:
                    await self._recreate_index_site()
                text = self._index_site
                headers = RESPONSE_HEADERS
            else:
                text = await self._template().render_async(storage=self._crawler.storage, selection=selection,
                                                           selection_str=selection_str, options=self._template_options)
                headers = RESPONSE_HEADERS_SELECTION

            response = web.Response(text=text, content_type="text/html", charset="utf-8",
                                    headers=headers)
            response.set_cookie("selection", selection_qs,
                                expires=SELECTION_COOKIE_EXPIRE, path="/" + self._plan_id + "/",
                                secure=not settings.DEBUG,  # secure in non-development mode
                                httponly=True, samesite="Lax")
            await response.prepare(request)
            await response.write_eof()

            if substitutions_have_changed:
                if selection:
                    await self._recreate_index_site()
                await get_scheduler(request).spawn(self._on_new_substitutions(affected_groups))
        except web.HTTPException as e:
            raise e from None
        except Exception:
            _LOGGER.exception("Exception occurred while handling request")
            response = web.Response(text=await self._error500_template().render_async(options=self._template_options),
                                    status=500, content_type="text/html", charset="utf-8", headers=RESPONSE_HEADERS)
        return response

    # /api/wait-for-updates
    @logger.request_wrapper
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
                                substitutions_have_changed, affected_groups = \
                                    await self._crawler.update(self._client_session)
                                if affected_groups:
                                    self._affected_groups = affected_groups
                                await ws.send_json({"type": "status", "status": self._crawler.storage.status})
                                if substitutions_have_changed:
                                    await self._recreate_index_site()
                                    await get_scheduler(request).spawn(self._on_new_substitutions(affected_groups))
            # no need to remove ws from self._websockets as self._websockets is a WeakSet
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass
        finally:
            _LOGGER.info(f"WebSocket connection closed: {ws.close_code}")
        return ws

    # /api/subscribe-push
    @logger.request_wrapper
    async def _subscribe_push_handler(self, request: web.Request):
        # noinspection PyBroadException
        try:
            data = await request.json()
            if data["is_active"]:
                self._db.add_push_subscription(self._plan_id, data["subscription"], data["selection"])
            else:
                self._db.delete_push_subscription(self._plan_id, data["subscription"]["endpoint"])
            self._db.commit()
            response = web.json_response({"ok": True})
        except Exception:
            _LOGGER.exception("Modifying push subscription failed")
            response = web.json_response({"ok": False}, status=400)
        return response

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

                async def send_push_notification(
                        subscription, common_affected_groups: Dict[int, Dict[str, Union[str, List[str]]]]
                ) -> Optional[sqlite3.Row]:
                    endpoint_hash = hash_endpoint(subscription["endpoint"])
                    _LOGGER.debug(f"Sending push notification to "
                                  f"{self._plan_id}-{endpoint_hash[:6]}")
                    # noinspection PyBroadException
                    try:
                        data = json.dumps({"affected_groups_by_day": common_affected_groups,
                                           "plan_id": self._plan_id,
                                           # status_datetime.timestamp() correctly assumes that datetime is local
                                           # time (status_datetime has no tzinfo) and returns the correct UTC
                                           # timestamp
                                           "timestamp": self._crawler.storage.status_datetime.timestamp()})

                        endpoint, data, headers = pywebpush.webpush(
                            subscription["subscription"], data,
                            vapid_private_key=settings.PRIVATE_VAPID_KEY,
                            vapid_claims={
                                "sub": settings.VAPID_SUB,
                                #"aud": endpoint_origin,  # aud is automatically set in webpush()
                                # 86400s=24h, but 5s less because otherwise, requests sometimes fail (exp must not
                                # be longer than 24 hours from the time the request is made)
                                "exp": int(time.time()) + 86395
                            },
                            ttl=86400,
                            curl=True)  # modifications to make this work: see beginning of this file
                        async with self._client_session.post(endpoint, data=data, headers=headers) as r:
                            if r.status >= 400:
                                # If status code is 404 or 410, the endpoints are unavailable, so delete the
                                # subscription. See https://autopush.readthedocs.io/en/latest/http.html#error-codes.
                                if r.status in (404, 410):
                                    _LOGGER.debug(f"No longer valid subscription "
                                                  f"{self._plan_id}-{endpoint_hash[:6]}: "
                                                  f"{r.status} {repr(await r.text())}")
                                    return subscription
                                else:
                                    _LOGGER.error(f"Could not send push notification to "
                                                  f"{self._plan_id}-{endpoint_hash[:6]}: "
                                                  f"{r.status} {repr(await r.text())}")
                            else:
                                _LOGGER.debug(
                                    f"Successfully sent push notification to {self._plan_id}-{endpoint_hash[:6]}: "
                                    f"{r.status} {repr(await r.text())}")
                    except Exception:
                        _LOGGER.exception(f"Could not send push notification to {self._plan_id}-{endpoint_hash[:6]}")
                    return None

                def iter_relevant_subscriptions():
                    subscription: sqlite3.Row
                    for subscription in self._db.iter_push_subscriptions(self._plan_id):
                        selection = subscription["selection"]
                        if selection is None:
                            # selection is None when all groups are selected
                            yield subscription, affected_groups
                        else:
                            intersection = {}
                            for expiry_time, day in affected_groups.items():
                                groups = day["groups"]
                                common_groups = [s for s in selection if any(s in g for g in groups)]
                                if common_groups:
                                    intersection[expiry_time] = {"name": day["name"], "groups": common_groups}
                            if intersection:
                                yield subscription, intersection

                subscriptions_to_delete: Iterable[sqlite3.Row] = await asyncio.gather(
                    *(send_push_notification(s, i) for s, i in iter_relevant_subscriptions()))
                for subscription in subscriptions_to_delete:
                    if subscription is not None:
                        self._db.delete_push_subscription(self._plan_id, subscription["endpoint"])
                self._db.commit()
        except Exception:
            _LOGGER.exception("Exception in on_new_substitutions background task")
