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
import sqlite3
import time
from _weakrefset import WeakSet
from email.utils import formatdate
from typing import Iterable, MutableSet, Optional, Tuple, Callable, Awaitable, List
from urllib.parse import urlparse

import aiocron
import pywebpush
import yarl
from aiohttp import web, WSMessage, WSMsgType
from aiojobs.aiohttp import get_scheduler_from_app

from . import log_helper
from .db import hash_endpoint, SubstitutionPlanDB
from .settings import Settings
from .subs_crawler.crawlers.base import BaseSubstitutionCrawler
from .subs_crawler.utils import split_selection

# Time when a "<plan-name>-selection" cookie expires. This is on 29th July, as on this date, summer holidays in Lower
# Saxony normally take place.
# Starting at 14h June, the cookie is set until the next year.
now = datetime.datetime.now()
SELECTION_COOKIE_EXPIRE = formatdate(time.mktime(
    datetime.datetime(now.year if now < datetime.datetime(now.year, 6, 14) else now.year + 1, 7, 29).timetuple()))
# Time for a cookie which should be deleted (Thu, 01 Jan 1970 00:00:00 GMT)
DELETE_COOKIE_EXPIRE = formatdate(0)


# Intercept pywebpush.WebPusher.as_curl() call in pywebpush.WebPusher.send() so that request can be made with aiohttp.
# A call to pywebpush.webpush(..., curl=True) will now return (endpoint, data, headers).
pywebpush.WebPusher.as_curl = lambda s, e, d, h: (e, d, h)


class SubstitutionPlan:
    def __init__(self, plan_id: str, crawler: BaseSubstitutionCrawler, render_func: Callable[..., Awaitable[str]]):
        self._plan_id = plan_id
        self._crawler = crawler
        self._render_func = render_func

        self._index_site = None
        self._websockets: MutableSet[web.WebSocketResponse] = WeakSet()

    def on_db_init(self, app: web.Application):
        self._crawler.last_version_id = app["db"].get_substitutions_version_id(self._plan_id)
        log_helper.PLAN_NAME_CONTEXTVAR.set(self._plan_id)
        app["logger"].debug(f"Last substitution version id is: {self._crawler.last_version_id!r}")
        log_helper.PLAN_NAME_CONTEXTVAR.set(None)

    def create_app(self, background_updates: List[str], static_path: Optional[str] = None) -> web.Application:
        app = web.Application()
        app.add_routes([
            web.get("/", self._root_handler),
            web.get("/api/wait-for-updates", self._wait_for_updates_handler),
            web.post("/api/subscribe-push", self._subscribe_push_handler)
        ])

        if static_path:
            app.router.add_static("/", static_path)

        async def update():
            log_helper.REQUEST_ID_CONTEXTVAR.set("bg-tasks")
            await self.update_substitutions(app)

        for cron_time in background_updates:
            aiocron.crontab(cron_time, func=update)

        return app

    async def cleanup(self):
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

    @log_helper.plan_name_wrapper
    async def update_substitutions(self, app: web.Application, fake_affected_groups=None):
        app["logger"].info("Updating substitutions...")
        if fake_affected_groups:
            changed = True
            affected_groups = fake_affected_groups
        else:
            changed, affected_groups = await self._crawler.update(app["client_session"])
        if changed:
            app["logger"].info("Substitutions have changed")
            self._index_site = await self._render_func(storage=self._crawler.storage)
            await get_scheduler_from_app(app).spawn(self._on_new_substitutions(app, affected_groups))
        elif app["settings"].debug:
            self._index_site = await self._render_func(storage=self._crawler.storage)

    # ===================
    # REQUEST HANDLERS

    # /
    @log_helper.plan_name_wrapper
    async def _root_handler(self, request: web.Request) -> web.Response:
        # noinspection PyBroadException
        try:
            redirect = False
            new_url = request.rel_url

            campaign = request.query.get("utm_campaign") or request.query.get("mtm_campaign")
            if campaign == "pwa_homescreen":
                new_query = {key: value for key, value in request.rel_url.query.items() if key not in ["utm_campaign", "mtm_campaign"] or value != "pwa_homescreen"}
                new_query["ref"] = "PWA"
                new_url = new_url.with_query(new_query)
                redirect = True

            if "all" not in request.query and "s" not in request.query:
                # "<plan-id>-selection" is the name of the cookie previously used to store the selection
                selection = None
                if "selection" in request.cookies and (s := request.cookies["selection"].strip()):
                    selection = s
                elif self._plan_id + "-selection" in request.cookies \
                        and (s := request.cookies[self._plan_id + "-selection"].strip()):
                    selection = s
                if selection is not None:
                    new_url = new_url.update_query(s=selection)
                else:
                    new_url = new_url.update_query("all")
                redirect = True

            if redirect:
                raise web.HTTPSeeOther(location=new_url)

            fake_affected_groups = None
            if request.app["settings"].debug:
                if "raise500" in request.query:
                    raise ValueError
                if "event" in request.query:
                    # in development, simulate new substitutions event by "event" parameter
                    fake_affected_groups = json.loads(request.query["event"])

            await self.update_substitutions(request.app, fake_affected_groups)

            selection, selection_str, selection_qs = self.parse_selection(request.url)

            headers = request.app["response_headers"]
            if not selection:
                text = self._index_site
            else:
                text = await self._render_func(storage=self._crawler.storage,
                                               selection=selection, selection_str=selection_str)
                headers["X-Robots-Tag"] = "noindex"

            response = web.Response(text=text, content_type="text/html", charset="utf-8",
                                    headers=headers)
            if request.cookies.get("selection", "").strip() != selection_qs:
                # appropriate cookie is missing, set it
                response.set_cookie("selection", selection_qs,
                                    expires=SELECTION_COOKIE_EXPIRE, path="/" + self._plan_id + "/",
                                    secure=not request.app["settings"].debug,  # secure in non-development mode
                                    httponly=True, samesite="Lax")
        except web.HTTPException:
            raise
        except Exception:
            request.app["logger"].exception("Exception while handling substitution request")
            # set info for error handling in server.py
            request["plan_id"] = self._plan_id
            raise
        return response

    # /api/wait-for-updates
    @log_helper.plan_name_wrapper
    async def _wait_for_updates_handler(self, request: web.Request):
        ws = web.WebSocketResponse()
        if not ws.can_prepare(request):
            raise web.HTTPNotFound()
        await ws.prepare(request)

        self._websockets.add(ws)
        try:
            msg: WSMessage
            async for msg in ws:
                request.app["logger"].debug("WebSocket: Got message " + str(msg))
                if msg.type in (WSMsgType.CLOSE, WSMsgType.ERROR):
                    return
                elif msg.type == WSMsgType.TEXT:
                    try:
                        data = msg.json()
                    except json.JSONDecodeError:
                        request.app["logger"].exception("WebSocket: Received malformed JSON message")
                    else:
                        if "type" in data:
                            if data["type"] == "get_status":
                                await self.update_substitutions(request.app)
                                await ws.send_json({"type": "status", "status": self._crawler.storage.status})
            # no need to remove ws from self._websockets as self._websockets is a WeakSet
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass
        finally:
            request.app["logger"].info(f"WebSocket connection closed: {ws.close_code}")
        return ws

    # /api/subscribe-push
    @log_helper.plan_name_wrapper
    async def _subscribe_push_handler(self, request: web.Request):
        db: SubstitutionPlanDB = request.app["db"]
        # noinspection PyBroadException
        try:
            data = await request.json()
            if data["is_active"]:
                db.add_push_subscription(request.app, self._plan_id, data["subscription"], data["selection"])
                if request.app["settings"].send_welcome_push_message:
                    if not await self.send_push_notification(
                            request.app,
                            data["subscription"],
                            {
                                "type": "generic_message",
                                "title": "Benachrichtigungen erfolgreich aktiviert!",
                                "body": "GaW Vertretungsplan"
                            }):
                        raise ValueError("Could not send push notification to newly subscribed endpoint")
            else:
                db.delete_push_subscription(request.app, self._plan_id, data["subscription"]["endpoint"])
            db.commit()
            response = web.json_response({"ok": True})
        except Exception:
            request.app["logger"].exception("Modifying push subscription failed")
            response = web.json_response({"ok": False}, status=400)
        return response

    async def send_push_notification(self, app: web.Application, subscription: dict, data) -> bool:
        logger = app["logger"]
        settings: Settings = app["settings"]

        endpoint_hash = hash_endpoint(subscription["endpoint"])
        # noinspection PyBroadException
        try:
            url = urlparse(subscription.get("endpoint"))  # copied from pywebpush.webpush
            aud = "{}://{}".format(url.scheme, url.netloc)

            logger.debug(f"Sending push notification to {self._plan_id}-{endpoint_hash[:6]} ({aud})")

            endpoint, data, headers = pywebpush.webpush(
                subscription, json.dumps(data),
                vapid_private_key=settings.private_vapid_key,
                vapid_claims={
                    "sub": settings.vapid_sub,
                    # "aud": endpoint_origin,  # aud is automatically set in webpush()
                    # 86400s=24h, but 5s less because otherwise, requests sometimes fail (exp must not
                    # be longer than 24 hours from the time the request is made)
                    "exp": int(time.time()) + 86395,
                    "aud": aud
                },
                content_encoding=settings.webpush_content_encoding,
                ttl=86400,
                curl=True)  # modifications to make this work: see beginning of this file
            async with app["client_session"].post(endpoint, data=data, headers=headers) as r:
                if r.status >= 400:
                    # If status code is 404 or 410, the endpoints are unavailable, so delete the
                    # subscription. See https://autopush.readthedocs.io/en/latest/http.html#error-codes.
                    if r.status in (404, 410):
                        logger.debug(f"No longer valid subscription {self._plan_id}-{endpoint_hash[:6]} ({aud}): "
                                     f"{r.status} {r.reason} {repr(await r.text())}")
                        return False
                    else:
                        logger.error(
                            f"Could not send push notification to {self._plan_id}-{endpoint_hash[:6]} ({aud}): "
                            f"{r.status} {r.reason} {repr(await r.text())}")
                else:
                    logger.debug(f"Successfully sent push notification to {self._plan_id}-{endpoint_hash[:6]}: "
                                 f"{r.status} {r.reason} {repr(await r.text())}")
        except Exception:
            logger.exception(f"Could not send push notification to {self._plan_id}-{endpoint_hash[:6]}")
        return True

    # background task on new substitutions
    async def _on_new_substitutions(self, app: web.Application, affected_groups):
        logger = app["logger"]
        db: SubstitutionPlanDB = app["db"]

        log_helper.REQUEST_ID_CONTEXTVAR.set(None)
        # noinspection PyBroadException
        try:
            db.set_substitutions_version_id(self._plan_id, self._crawler.last_version_id)
            logger.debug(f"Changed last substitution version id to: {self._crawler.last_version_id!r}")

            # WEBSOCKETS
            logger.debug(f"Sending update event via WebSocket connection to {len(self._websockets)} clients")
            for ws in self._websockets:
                # noinspection PyBroadException
                try:
                    await ws.send_json({"type": "status", "status": self._crawler.storage.status})
                except Exception:
                    pass

            # PUSH NOTIFICATIONS
            if affected_groups:
                logger.debug("Sending affected groups via push messages")

                def iter_relevant_subscriptions():
                    row: sqlite3.Row
                    for row in db.iter_push_subscriptions(self._plan_id):
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
                    if not await self.send_push_notification(app, subscription, data):
                        return subscription["endpoint"]

                endpoints_to_delete: Iterable[Optional[str]] = await asyncio.gather(
                    *(send_notification(s, c) for s, c in iter_relevant_subscriptions()))
                for endpoint in endpoints_to_delete:
                    if endpoint is not None:
                        db.delete_push_subscription(app, self._plan_id, endpoint)
                db.commit()
        except Exception:
            logger.exception("Exception in on_new_substitutions background task")
