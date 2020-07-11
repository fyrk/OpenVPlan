import asyncio
import logging
from typing import List

import aiohttp
import jinja2
from aiohttp import web, WSMessage

from .. import config
from ..substitution_plan.loader import BaseSubstitutionLoader
from ..substitution_plan.utils import split_selection


logger = logging.getLogger("gawvertretung")


class SubstitutionPlan:
    def __init__(self, substitution_loader: BaseSubstitutionLoader, template: jinja2.Template,
                 error500_template: jinja2.Template):
        self._substitution_loader = substitution_loader
        self._template = template
        self._error500_template = error500_template
        self._index_site = None
        self._event_new_substitutions = asyncio.Event()

    def _prettify_selection(self, selection: List[str]) -> str:
        return ", ".join(selection)

    async def _recreate_index_site(self):
        self._index_site = await self._template.render_async(storage=self._substitution_loader.storage)

    async def handler(self, request: web.Request) -> web.Response:
        logger.info("Request", request)
        substitutions_have_changed = False
        # noinspection PyBroadException
        try:
            substitutions_have_changed = await self._substitution_loader.update(request.app["client_session"]) \
                                         or config.get_bool("dev")
            if "event" in request.query and config.get_bool("dev"):
                # in development, simulate new substitutions event by "event" parameter
                self._event_new_substitutions.set()
                self._event_new_substitutions.clear()
            if "s" in request.query and (selection := split_selection(",".join(request.query.getall("s")))):
                # noinspection PyUnboundLocalVariable
                selection_str = self._prettify_selection(selection)
                selection = [s.upper() for s in selection]
                response = web.Response(text=await self._template.render_async(
                    storage=self._substitution_loader.storage, selection=selection, selection_str=selection_str),
                                    content_type="text/html", charset="utf-8")
            else:
                if substitutions_have_changed:
                    await self._recreate_index_site()
                response = web.Response(text=self._index_site, content_type="text/html", charset="utf-8")
                if substitutions_have_changed:
                    await response.prepare(request)
                    await response.write_eof()
                    self._event_new_substitutions.set()
                    self._event_new_substitutions.clear()
                return response
        except Exception:
            logger.exception("Exception occurred while handling request")
            response = web.Response(text=await self._error500_template.render_async(), content_type="text/html",
                                    charset="utf-8")
        if substitutions_have_changed:
            await response.prepare(request)
            await response.write_eof()
            self._event_new_substitutions.set()
            self._event_new_substitutions.clear()
            await self._recreate_index_site()
        return response

    async def wait_for_update_handler(self, request: web.Request):
        logger.info("wait-for-update " + str(request.url))
        ws = web.WebSocketResponse()
        await ws.prepare(request)

        async def listen():
            msg: WSMessage
            async for msg in ws:
                logger.debug("Got message " + str(msg))
                if msg.type in (aiohttp.WSMsgType.CLOSE, aiohttp.WSMsgType.ERROR):
                    return

        async def send():
            while True:
                await self._event_new_substitutions.wait()
                logger.debug("Send substitutions")
                await ws.send_json({"hello": "world"})

        listener = asyncio.ensure_future(send())
        sender = asyncio.ensure_future(listen())
        await asyncio.wait((sender, listener), return_when=asyncio.FIRST_COMPLETED)
        listener.cancel()
        sender.cancel()
        return ws


class SubstitutionPlanUppercaseSelection(SubstitutionPlan):
    def _prettify_selection(self, selection: List[str]) -> str:
        return super()._prettify_selection(selection).upper()
