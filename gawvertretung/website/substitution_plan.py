import asyncio
import datetime
import json
import logging
import time
from email.utils import formatdate
from typing import List, Optional, Dict

import jinja2
import pywebpush
from aiohttp import web, WSMessage, WSMsgType, ClientSession
from cryptography.hazmat.primitives import serialization
from py_vapid.jwt import sign
from py_vapid.utils import b64urlencode

from .. import config
from ..db.db import SubstitutionPlanDBStorage
from ..substitution_plan.loader import BaseSubstitutionLoader
from ..substitution_plan.utils import split_selection

_LOGGER = logging.getLogger("gawvertretung")

# Time when a "<plan-name>-selection" cookie expires. This is on 29th July, as on this date, summer holidays in Lower
# Saxony normally take place.
SELECTION_COOKIE_EXPIRE = formatdate(time.mktime(datetime.datetime(datetime.datetime.now().year, 7, 29).timetuple()))
# Time for a cookie which should be deleted (Thu, 01 Jan 1970 00:00:00 GMT)
DELETE_COOKIE_EXPIRE = formatdate(0)


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

    @property
    def name(self):
        return self._name

    @property
    def app(self):
        return self._app

    def serialize(self, filepath: str):
        self._substitution_loader.serialize(filepath)
        self._serialization_filepath = filepath

    def deserialize(self, filepath: str):
        self._substitution_loader.deserialize(filepath)
        self._serialization_filepath = filepath

    def _prettify_selection(self, selection: List[str]) -> str:
        return ", ".join(selection)

    async def _recreate_index_site(self):
        self._index_site = await self._template.render_async(storage=self._substitution_loader.storage)

    async def _on_new_substitutions(self, affected_groups: Optional[Dict[str, List[str]]]):
        if not config.get_bool("dev"):
            self._event_new_substitutions.set()
            self._event_new_substitutions.clear()
        if affected_groups:
            _LOGGER.debug("Sending affected groups via push messages: " + str(affected_groups))

            async def send_push_notification(subscription_entry, common_affected_groups: Dict[str, List[str]]):
                endpoint_hash = subscription_entry["endpoint_hash"]
                endpoint_origin = subscription_entry["endpoint_origin"]
                _LOGGER.debug("Sending push notification to " + endpoint_hash)
                # noinspection PyBroadException
                try:
                    data = json.dumps({"affected_groups_by_day": common_affected_groups, "plan_type": self._name,
                                       "status": self._substitution_loader.storage.status})
                    encoded = pywebpush.WebPusher(subscription_info=subscription_entry["subscription"]) \
                        .encode(data)
                    headers = {"content-encoding": "aes128gcm"}
                    if "crypto_key" in encoded:
                        headers["crypto-key"] = "dh=" + encoded["crypto_key"].decode("utf-8")
                    if "salt" in encoded:
                        headers["encryption"] = "salt=" + encoded["salt"].decode("utf-8")

                    vv = pywebpush.Vapid.from_string(private_key=config.get_str("private_vapid_key"))
                    sig = sign({
                        "sub": config.get_str("vapid_sub"),
                        "aud": endpoint_origin,
                        "exp": str(int(time.time()) + (24 * 60 * 60))  # 24 hours (maximum)
                    }, vv.private_key)
                    pkey = vv.public_key.public_bytes(
                        serialization.Encoding.X962,
                        serialization.PublicFormat.UncompressedPoint
                    )
                    headers["ttl"] = str(86400)
                    headers["Authorization"] = "{schema} t={t},k={k}".format(
                            schema="vapid",
                            t=sig,
                            k=b64urlencode(pkey)
                        )

                    async with self.client_session.post(subscription_entry["endpoint"], data=encoded["body"],
                                                        headers=headers) as r:
                        if r.status >= 400:
                            _LOGGER.error(f"Could not send push notification to {endpoint_hash} ({endpoint_origin}): "
                                          f"{r.status} {repr(await r.text())}")
                            # if status code is 404 or 410, the endpoints are unavailable, so delete the subscription
                            # See https://autopush.readthedocs.io/en/latest/http.html#error-codes
                            if r.status in (404, 410):
                                return subscription_entry
                        else:
                            _LOGGER.debug(f"Successfully sent push notification to {endpoint_hash}: {r.status} "
                                          f"{repr(await r.text())}")
                except Exception:
                    _LOGGER.exception(f"Could not send push notification to {subscription_entry['endpoint_hash']} "
                                      f"({endpoint_origin})")
                return None

            subscription_entries_to_delete = await asyncio.gather(
                *(send_push_notification(subscription, common_affected_groups)
                  for subscription, common_affected_groups in
                  self.storage.iter_active_push_subscriptions(affected_groups)))
            for subscription_entry in subscription_entries_to_delete:
                if subscription_entry is not None:
                    self.storage.delete_push_subscription(subscription_entry)
        self.serialize(self._serialization_filepath)

    async def _base_handler(self, request: web.Request) -> web.Response:
        _LOGGER.info(f"{request.method} {request.path}")
        # noinspection PyBroadException
        try:
            substitutions_have_changed, affected_groups = \
                await self._substitution_loader.update(self.client_session)
            substitutions_have_changed = substitutions_have_changed or config.get_bool("dev")
            if "event" in request.query and config.get_bool("dev"):
                # in development, simulate new substitutions event by "event" parameter
                substitutions_have_changed = True
                affected_groups = json.loads(request.query["event"])
            if "s" in request.query \
                    and (selection := split_selection(selection_qs := ",".join(request.query.getall("s")))):
                # noinspection PyUnboundLocalVariable
                selection_str = self._prettify_selection(selection)
                selection = [s.upper() for s in selection]
                response = web.Response(text=await self._template.render_async(
                    storage=self._substitution_loader.storage, selection=selection, selection_str=selection_str),
                                        content_type="text/html", charset="utf-8")
                # unfortunately, "same_site" parameter is not in a realease yet (see
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
                cookie["samesite"] = "Strict"
                if substitutions_have_changed:
                    await response.prepare(request)
                    await response.write_eof()
                    await self._on_new_substitutions(affected_groups)
                    await self._recreate_index_site()
            else:
                if "all" not in request.query and self._name + "-selection" in request.cookies and \
                        request.cookies[self._name + "-selection"].strip():
                    raise web.HTTPSeeOther(
                        location="/" + self._name + "/?s=" + request.cookies[self._name + "-selection"]
                    )
                if substitutions_have_changed:
                    await self._recreate_index_site()
                response = web.Response(text=self._index_site, content_type="text/html", charset="utf-8")
                # response.del_cookie(self._name + "-selection")
                response.cookies[self._name + "-selection"] = ""
                cookie = response.cookies[self._name + "-selection"]
                cookie["expires"] = DELETE_COOKIE_EXPIRE
                cookie["path"] = "/" + self._name + "/"
                if not config.get_bool("dev"):
                    cookie["secure"] = True
                cookie["httponly"] = True
                cookie["samesite"] = "Strict"
                if substitutions_have_changed:
                    await response.prepare(request)
                    await response.write_eof()
                    await self._on_new_substitutions(affected_groups)
                return response
        except web.HTTPException as e:
            raise e from None
        except Exception:
            _LOGGER.exception("Exception occurred while handling request")
            response = web.Response(text=await self._error500_template.render_async(), status=500,
                                    content_type="text/html", charset="utf-8")
        return response

    async def _wait_for_updates_handler(self, request: web.Request):
        ws = web.WebSocketResponse()
        if not ws.can_prepare(request):
            raise web.HTTPNotFound()
        _LOGGER.info(f"WEBSOCKET {request.path}")
        await ws.prepare(request)

        async def listen():
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
                                    if self._substitution_loader.storage.status != data["status"]:
                                        # inform client that substitutions are not up-to-date
                                        await send_new_substitutions_message()

        async def send_new_substitutions_message():
            return await ws.send_json({"type": "new_substitutions"})

        async def send():
            while True:
                await self._event_new_substitutions.wait()
                _LOGGER.debug("Send substitutions")
                await send_new_substitutions_message()

        listener = asyncio.ensure_future(send())
        sender = asyncio.ensure_future(listen())
        await asyncio.wait((sender, listener), return_when=asyncio.FIRST_COMPLETED)
        listener.cancel()
        sender.cancel()
        return ws

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
        self._app = web.Application()
        self._app.add_routes([
            web.get("/", self._base_handler),
            web.get("/api/wait-for-updates", self._wait_for_updates_handler),
            web.post("/api/subscribe-push", self._subscribe_push_handler)
        ])
        if static_path:
            self._app.router.add_static("/", static_path)
        return self._app


class SubstitutionPlanUppercaseSelection(SubstitutionPlan):
    def _prettify_selection(self, selection: List[str]) -> str:
        return super()._prettify_selection(selection).upper()
