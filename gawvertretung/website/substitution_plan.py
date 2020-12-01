import asyncio
import datetime
import json
import logging
import time
from _weakrefset import WeakSet
from email.utils import formatdate
from typing import Dict, List, MutableSet, Optional

import jinja2
import pywebpush
from aiohttp import ClientSession, web, WSMessage, WSMsgType
from cryptography.hazmat.primitives import serialization
from py_vapid.jwt import sign
from py_vapid.utils import b64urlencode

from .. import config, logger
from ..db.db import SubstitutionPlanDBStorage
from ..substitution_plan.loader import BaseSubstitutionLoader
from ..substitution_plan.utils import split_selection

_LOGGER = logging.getLogger("gawvertretung")

# Time when a "<plan-name>-selection" cookie expires. This is on 29th July, as on this date, summer holidays in Lower
# Saxony normally take place.
now = datetime.datetime.now()
SELECTION_COOKIE_EXPIRE = formatdate(time.mktime(
    datetime.datetime(now.year if now < datetime.datetime(now.year, 7, 29) else now.year+1, 7, 29).timetuple()))
# Time for a cookie which should be deleted (Thu, 01 Jan 1970 00:00:00 GMT)
DELETE_COOKIE_EXPIRE = formatdate(0)

RESPONSE_HEADERS = {
    "Content-Security-Policy": "default-src 'self'; img-src 'self' data:; "
                               "script-src-elem 'self' 'sha256-Rn05miOR4sI8OxFu9H46X31LzrYohKIkUCoRcexpDzM='; "
                               "connect-src 'self' " + ("ws:" if config.get_bool("dev") else "wss:"),
    "Strict-Transport-Security": "max-age=63072000",
    "Referrer-Policy": "same-origin",
    "X-Content-Type-Options": "nosniff",
    "X-Frame-Options": "DENY",
    "X-XSS-Protection": "1",
    "X-Robots-Tag": "noarchive, notranslate"
}

RESPONSE_HEADERS_SELECTION = {
    **RESPONSE_HEADERS,
    "X-Robots-Tag": "noindex"
}


class SubstitutionPlan:
    def __init__(self, name: str, substitution_loader: BaseSubstitutionLoader, template: jinja2.Template,
                 error500_template: jinja2.Template):
        self._name = name
        self._substitution_loader = substitution_loader
        self._template = template
        self._error500_template = error500_template
        self._event_new_substitutions = asyncio.Event()

        self._index_site = None
        self._serialization_filepath = None
        self.storage: Optional[SubstitutionPlanDBStorage] = None
        self.client_session: Optional[ClientSession] = None
        self._app: Optional[web.Application] = None
        self._websockets: MutableSet[web.WebSocketResponse] = WeakSet()
        self._affected_groups = None  # affected groups are passed from self._root_handler to self._background_tasks

    @property
    def name(self):
        return self._name

    @property
    def app(self):
        return self._app

    async def serialize(self, filepath: str):
        self._substitution_loader.serialize(filepath)
        self._serialization_filepath = filepath

    async def deserialize(self, filepath: str):
        self._substitution_loader.deserialize(filepath)
        self._serialization_filepath = filepath
        if self._substitution_loader.storage is not None:
            await self._recreate_index_site()

    def _prettify_selection(self, selection: List[str]) -> str:
        return ", ".join(selection)

    async def _recreate_index_site(self):
        self._index_site = await self._template.render_async(storage=self._substitution_loader.storage)

    # ===================
    # REQUEST HANDLERS

    # /
    @logger.request_wrapper
    async def _root_handler(self, request: web.Request) -> web.Response:
        # noinspection PyBroadException
        try:
            if "all" not in request.query and "s" not in request.query:
                if self._name + "-selection" in request.cookies and \
                        request.cookies[self._name + "-selection"].strip():
                    raise web.HTTPSeeOther(
                        location="/" + self._name + "/?s=" + request.cookies[self._name + "-selection"]
                    )
                else:
                    raise web.HTTPSeeOther(location="/" + self._name + "/?all")
            substitutions_have_changed, affected_groups = await self._substitution_loader.update(self.client_session)
            if affected_groups:
                self._affected_groups = affected_groups
            if "event" in request.query and config.get_bool("dev"):
                # in development, simulate new substitutions event by "event" parameter
                substitutions_have_changed = True
                self._affected_groups = json.loads(request.query["event"])
            if substitutions_have_changed:
                _LOGGER.info("SUBSTITUTIONS HAVE CHANGED")
            if "s" in request.query \
                    and (selection := split_selection(selection_qs := ",".join(request.query.getall("s")))):
                # noinspection PyUnboundLocalVariable
                selection_str = self._prettify_selection(selection)
                selection = [s.upper() for s in selection]
                response = web.Response(text=await self._template.render_async(
                    storage=self._substitution_loader.storage, selection=selection, selection_str=selection_str),
                                        content_type="text/html", charset="utf-8", headers=RESPONSE_HEADERS_SELECTION)
                # unfortunately, "same_site" parameter is not in a release yet (see
                # https://github.com/aio-libs/aiohttp/pull/4224), so access SimpleCookie directly
                # response.set_cookie(self._name + "-selection", selection_qs, expires=SELECTION_COOKIE_EXPIRE)
                # noinspection PyUnboundLocalVariable
                response.cookies[self._name + "-selection"] = selection_qs
                cookie = response.cookies[self._name + "-selection"]
                cookie["expires"] = SELECTION_COOKIE_EXPIRE
                cookie["path"] = "/" + self._name + "/"
                if not config.get_bool("dev"):
                    cookie["secure"] = True
                cookie["httponly"] = True
                cookie["samesite"] = "Lax"
                if substitutions_have_changed:
                    await response.prepare(request)
                    await response.write_eof()
                    await self._recreate_index_site()
                    self._event_new_substitutions.set()
            else:
                if substitutions_have_changed or config.get_bool("dev"):
                    await self._recreate_index_site()
                response = web.Response(text=self._index_site, content_type="text/html", charset="utf-8",
                                        headers=RESPONSE_HEADERS)
                # response.del_cookie(self._name + "-selection")
                response.cookies[self._name + "-selection"] = ""
                cookie = response.cookies[self._name + "-selection"]
                cookie["expires"] = DELETE_COOKIE_EXPIRE
                cookie["path"] = "/" + self._name + "/"
                if not config.get_bool("dev"):
                    cookie["secure"] = True
                cookie["httponly"] = True
                cookie["samesite"] = "Lax"
                if substitutions_have_changed:
                    await response.prepare(request)
                    await response.write_eof()
                    self._event_new_substitutions.set()
                return response
        except web.HTTPException as e:
            raise e from None
        except Exception:
            _LOGGER.exception("Exception occurred while handling request")
            response = web.Response(text=await self._error500_template.render_async(), status=500,
                                    content_type="text/html", charset="utf-8", headers=RESPONSE_HEADERS)
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
                            if data["type"] == "check_status":
                                if "status" in data:
                                    substitutions_have_changed, affected_groups = \
                                        await self._substitution_loader.update(self.client_session)
                                    if affected_groups:
                                        self._affected_groups = affected_groups
                                    if self._substitution_loader.storage.status != data["status"]:
                                        # inform client that substitutions are not up-to-date
                                        await ws.send_json({"type": "new_substitutions"})
                                    if substitutions_have_changed:
                                        await self._recreate_index_site()
                                        self._event_new_substitutions.set()
        finally:
            self._websockets.remove(ws)
        return ws

    # /api/subscribe-push
    @logger.request_wrapper
    async def _subscribe_push_handler(self, request: web.Request):
        # noinspection PyBroadException
        try:
            data = await request.json()
            self.storage.add_push_subscription(data["subscription"], data["selection"], data["is_active"])
        except Exception:
            _LOGGER.exception("Subscribing push service failed")
            return web.json_response({"ok": False}, status=400)
        return web.json_response({"ok": True})

    def create_app(self, static_path: Optional[str] = None) -> web.Application:
        async def create_background_tasks(app):
            app["background_tasks"] = asyncio.create_task(self._background_tasks())

        async def cleanup_background_tasks(app):
            app["background_tasks"].cancel()
            await app["background_tasks"]

        self._app = web.Application()
        self._app.on_startup.append(create_background_tasks)
        self._app.on_cleanup.append(cleanup_background_tasks)
        self._app.add_routes([
            web.get("/", self._root_handler),
            web.get("/api/wait-for-updates", self._wait_for_updates_handler),
            web.post("/api/subscribe-push", self._subscribe_push_handler)
        ])
        if static_path:
            self._app.router.add_static("/", static_path)
        return self._app

    async def _background_tasks(self):
        token = logger.PLAN_NAME_CONTEXTVAR.set(self._name)
        try:
            while True:
                _LOGGER.debug("Waiting for new substitutions event...")
                await self._event_new_substitutions.wait()
                self._event_new_substitutions.clear()
                affected_groups = self._affected_groups
                self._affected_groups = None

                # SERIALIZE
                await self.serialize(self._serialization_filepath)

                # WEBSOCKETS
                _LOGGER.debug("Sending update event via WebSockets")
                for ws in self._websockets:
                    await ws.send_json({"type": "new_substitutions"})

                # PUSH NOTIFICATIONS
                if affected_groups:
                    _LOGGER.debug("Sending affected groups via push messages: " + str(affected_groups))

                    async def send_push_notification(subscription_entry, common_affected_groups: Dict[str, List[str]]):
                        endpoint_hash = subscription_entry["endpoint_hash"]
                        endpoint_origin = subscription_entry["endpoint_origin"]
                        _LOGGER.debug("Sending push notification to " + endpoint_hash)
                        # noinspection PyBroadException
                        try:
                            data = json.dumps({"affected_groups_by_day": common_affected_groups,
                                               "plan_type": self._name,
                                               "status": self._substitution_loader.storage.status})
                            encoded = \
                                pywebpush.WebPusher(subscription_info=subscription_entry["subscription"]).encode(data)
                            headers = {"content-encoding": "aes128gcm"}
                            if "crypto_key" in encoded:
                                headers["crypto-key"] = "dh=" + encoded["crypto_key"].decode("utf-8")
                            if "salt" in encoded:
                                headers["encryption"] = "salt=" + encoded["salt"].decode("utf-8")

                            vv = pywebpush.Vapid.from_string(private_key=config.get_str("private_vapid_key"))
                            sig = sign({
                                "sub": config.get_str("vapid_sub"),
                                "aud": endpoint_origin,
                                # 86400s=24h, but 5s less because otherwise, requests sometimes fail (exp must not be
                                # longer than 24 hours from the time the request is made)
                                "exp": int(time.time()) + 86395
                            }, vv.private_key)
                            pkey = vv.public_key.public_bytes(serialization.Encoding.X962,
                                                              serialization.PublicFormat.UncompressedPoint)
                            headers["ttl"] = str(86400)
                            headers["Authorization"] = f"{'vapid'} t={sig},k={b64urlencode(pkey)}"

                            async with self.client_session.post(subscription_entry["endpoint"], data=encoded["body"],
                                                                headers=headers) as r:
                                if r.status >= 400:
                                    _LOGGER.error(
                                        f"Could not send push notification to {endpoint_hash} ({endpoint_origin}): "
                                        f"{r.status} {repr(await r.text())}")
                                    # If status code is 404 or 410, the endpoints are unavailable, so delete the
                                    # subscription. See https://autopush.readthedocs.io/en/latest/http.html#error-codes.
                                    if r.status in (404, 410):
                                        return subscription_entry
                                else:
                                    _LOGGER.debug(f"Successfully sent push notification to {endpoint_hash}: {r.status} "
                                                  f"{repr(await r.text())}")
                        except Exception:
                            _LOGGER.exception(f"Could not send push notification to "
                                              f"{subscription_entry['endpoint_hash']} ({endpoint_origin})")
                        return None

                    subscription_entries_to_delete = await asyncio.gather(
                        *(send_push_notification(subscription, common_affected_groups)
                          for subscription, common_affected_groups in
                          self.storage.iter_active_push_subscriptions(affected_groups)))
                    for subscription_entry in subscription_entries_to_delete:
                        if subscription_entry is not None:
                            self.storage.delete_push_subscription(subscription_entry)
        finally:
            logger.PLAN_NAME_CONTEXTVAR.reset(token)


class SubstitutionPlanUppercaseSelection(SubstitutionPlan):
    def _prettify_selection(self, selection: List[str]) -> str:
        return super()._prettify_selection(selection).upper()
