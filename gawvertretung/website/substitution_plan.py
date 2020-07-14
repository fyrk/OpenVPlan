import asyncio
import datetime
import logging
import time
from email.utils import formatdate
from typing import List, Optional

import jinja2
import pywebpush
from cryptography.hazmat.primitives import serialization
from py_vapid.jwt import sign
from py_vapid.utils import b64urlencode
from aiohttp import web, WSMessage, WSMsgType, ClientSession

from .. import config
from ..db.db import SubstitutionPlanDBStorage
from ..substitution_plan.loader import BaseSubstitutionLoader
from ..substitution_plan.utils import split_selection

_LOGGER = logging.getLogger("gawvertretung")

# Time when a "<plan-name>-selection" cookie expires. This is on 29th July, as on this date, summer holidays in Lower
# Saxony normally take place.
SELECTION_COOKIE_EXPIRE = formatdate(time.mktime(datetime.datetime(datetime.datetime.now().year, 7, 29).timetuple()))


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

    async def _on_new_substitutions(self, affected_groups: Optional[List[str]]):
        if not config.get_bool("dev"):
            self._event_new_substitutions.set()
            self._event_new_substitutions.clear()
        if affected_groups:
            _LOGGER.debug("Sending affected groups via push messages: " + str(affected_groups))

            async def send_push_notification(subscription_entry, common_affected_groups):
                endpoint_hash = subscription_entry["endpoint_hash"]
                endpoint_origin = subscription_entry["endpoint_origin"]
                _LOGGER.debug("Sending push notification to " + endpoint_hash)
                # noinspection PyBroadException
                try:
                    encoded = pywebpush.WebPusher(subscription_info=subscription_entry["subscription"]) \
                        .encode(", ".join(common_affected_groups))
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
                    print("headers:", headers)

                    async with self.client_session.post(subscription_entry["endpoint"], data=encoded["body"],
                                                        headers=headers) as r:
                        if r.status >= 400:
                            _LOGGER.error(f"Could not send push notification to {endpoint_hash} ({endpoint_origin}): "
                                          f"{r.status} {repr(await r.text())}")
                        else:
                            _LOGGER.debug(f"Successfully sent push notification to {endpoint_hash}: {r.status} "
                                          f"{repr(await r.text())}")
                except Exception:
                    _LOGGER.exception(f"Could not send push notification to {subscription_entry['endpoint_hash']} "
                                      f"({endpoint_origin})")

            await asyncio.gather(*(send_push_notification(subscription, common_affected_groups)
                                   for subscription, common_affected_groups in
                                   self.storage.iter_active_push_subscriptions(affected_groups)))
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
                affected_groups = [s.strip() for s in request.query["event"].split(",")]
            if "s" in request.query and (selection := split_selection(selection_qs := ",".join(request.query.getall("s")))):
                # noinspection PyUnboundLocalVariable
                selection_str = self._prettify_selection(selection)
                selection = [s.upper() for s in selection]
                response = web.Response(text=await self._template.render_async(
                    storage=self._substitution_loader.storage, selection=selection, selection_str=selection_str),
                                        content_type="text/html", charset="utf-8")
                # noinspection PyUnboundLocalVariable
                response.set_cookie(self._name + "-selection", selection_qs, expires="")
                if substitutions_have_changed:
                    await response.prepare(request)
                    await response.write_eof()
                    await self._on_new_substitutions(affected_groups)
                    await self._recreate_index_site()
            else:
                if "all" not in request.query and self._name + "-selection" in request.cookies:
                    raise web.HTTPSeeOther(
                        location="/" + self._name + "/?s=" + request.cookies[self._name + "-selection"]
                    )
                if substitutions_have_changed:
                    await self._recreate_index_site()
                response = web.Response(text=self._index_site, content_type="text/html", charset="utf-8")
                response.del_cookie(self._name + "-selection")
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
                _LOGGER.debug("Got message " + str(msg))
                if msg.type in (WSMsgType.CLOSE, WSMsgType.ERROR):
                    return

        async def send():
            while True:
                await self._event_new_substitutions.wait()
                _LOGGER.debug("Send substitutions")
                await ws.send_json({"hello": "world"})

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

    def create_app(self) -> web.Application:
        self._app = web.Application()
        self._app.add_routes([
            web.get("/", self._base_handler),
            web.get("/api/wait-for-updates", self._wait_for_updates_handler),
            web.post("/api/subscribe-push", self._subscribe_push_handler)
        ])
        return self._app


class SubstitutionPlanUppercaseSelection(SubstitutionPlan):
    def _prettify_selection(self, selection: List[str]) -> str:
        return super()._prettify_selection(selection).upper()
