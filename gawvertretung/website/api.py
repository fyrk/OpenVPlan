import logging

from aiohttp import web

from ..substitution_plan.loader import BaseSubstitutionLoader
from ..substitution_plan.utils import split_selection

logger = logging.getLogger()


class SubstitutionAPI:
    def __init__(self, substitution_loader: BaseSubstitutionLoader):
        self.substitution_loader = substitution_loader

    async def handler(self, request: web.Request):
        def handle_error(response, description=None):
            data = {"ok": False, "error": response}
            if description:
                data["message"] = description
            return web.json_response(data)

        if "s" in request.query:
            selection = split_selection(",".join(request.query.getall("s")))
        else:
            selection = None
        return web.json_response(self.substitution_loader.storage.to_data(selection))
