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

import datetime
import json
import os
from functools import partial
from typing import Optional

import aiocron
import jinja2
from aiohttp import client, web
from aiojobs.aiohttp import setup, get_scheduler_from_app

import settings
import subs_crawler
from settings import settings
from website import logger
from website.db import SubstitutionPlanDB
from website.substitution_plan import RESPONSE_HEADERS, SubstitutionPlan

for directory in (
    settings.DATA_DIR,
    settings.CACHE_DIR,
    os.path.dirname(settings.LOGFILE)
):
    os.makedirs(directory, exist_ok=True)


_LOGGER = logger.get_logger()

env = jinja2.Environment(
    loader=jinja2.FileSystemLoader("assets/templates"),
    bytecode_cache=jinja2.FileSystemBytecodeCache(os.path.join(settings.CACHE_DIR)),
    enable_async=True,
    autoescape=True,
    trim_blocks=True,
    lstrip_blocks=True,
    auto_reload=settings.DEBUG
)

_CACHE_BUSTING: Optional[dict] = None

def template_static(path: str):
    if path in _CACHE_BUSTING:
        return "/" + path + "?v=" + _CACHE_BUSTING[path]
    _LOGGER.warn(f"Missing cache busting parameter for '{path}'")
    return "/" + path


async def render_template(name: str, **kwargs):
    global _CACHE_BUSTING
    if settings.DEBUG or _CACHE_BUSTING is None:  # always reload cache_busting.json in debug mode
        with open("assets/cache_busting.json", "r") as f:
            _CACHE_BUSTING = json.load(f)
    ferien = settings.ENABLE_FERIEN
    if ferien and settings.FERIEN_START and settings.FERIEN_END and \
            not (settings.FERIEN_START < datetime.datetime.now() < settings.FERIEN_END):
        ferien = False
    return await env.get_template(name).render_async(
        static=template_static, plausible=settings.PLAUSIBLE, ferien=ferien,
        **kwargs)


@web.middleware
async def error_middleware(request: web.Request, handler):
    # noinspection PyBroadException
    try:
        return await handler(request)
    except web.HTTPException as e:
        if e.status == 404:
            return web.Response(text=await render_template("error-404.min.html"),
                                status=404, content_type="text/html", charset="utf-8", headers=RESPONSE_HEADERS)
        raise
    except Exception:
        _LOGGER.exception(f"{request.method} {request.path} Exception while handling request")
    except BaseException:
        _LOGGER.exception(f"{request.method} {request.path} BaseException while handling request")
        raise
    plan_id = request.get("plan_id")
    try:
        original_data_link = settings.SUBSTITUTION_PLANS[plan_id]["template_options"]["original_data_link"]
    except:
        original_data_link = \
            settings.SUBSTITUTION_PLANS[settings.DEFAULT_PLAN_ID]["template_options"]["original_data_link"]
    return web.Response(text=await render_template("error-500.min.html",
                                                   plan_id=plan_id, original_data_link=original_data_link),
                        status=500, content_type="text/html", charset="utf-8", headers=RESPONSE_HEADERS)


def template_handler(name: str, response_headers: dict = None, render_args: dict = None):
    if response_headers:
        response_headers = {**RESPONSE_HEADERS, **response_headers}
    else:
        response_headers = RESPONSE_HEADERS
    if not render_args:
        render_args = {}
    # noinspection PyUnusedLocal
    async def handler(request: web.Request):
        response = web.Response(text=await render_template(name, **render_args),
                                content_type="text/html", headers=response_headers)
        await response.prepare(request)
        await response.write_eof()
        return response
    return handler


def redirect_handler(location, **kwargs):
    async def handler(r):
        raise web.HTTPMovedPermanently(location, **kwargs)
    return handler


async def client_session_context(app: web.Application):
    _LOGGER.debug(f"Create ClientSession (headers: {settings.REQUEST_HEADERS})")
    session = client.ClientSession(headers=settings.REQUEST_HEADERS)
    for substitution_plan in app["substitution_plans"].values():
        substitution_plan.set_client_session(session)
    yield
    await session.close()


async def databases_context(app: web.Application):
    db = SubstitutionPlanDB(os.path.join(settings.DATA_DIR, "db.sqlite3"))
    for substitution_plan in app["substitution_plans"].values():
        substitution_plan.set_db(db)
    yield
    db.close()


async def shutdown(app):
    _LOGGER.info("Shutting down...")
    for subs_plan in app["substitution_plans"].values():
        await subs_plan.close()
    await logger.cleanup()


def get_update_subs_func(app, plan):
    async def update():
        logger.REQUEST_ID_CONTEXTVAR.set("bg-tasks")
        await plan.update_substitutions(get_scheduler_from_app(app))
    return update


async def app_factory(start_log_msg):
    await logger.init(settings.LOGFILE)
    _LOGGER.info(start_log_msg)

    app = web.Application(middlewares=[logger.logging_middleware, error_middleware])
    setup(app)

    app["substitution_plans"] = {}

    app.on_shutdown.append(shutdown)

    for plan_id, plan_config in settings.SUBSTITUTION_PLANS.items():
        crawler_id = plan_config["crawler"]["name"]
        try:
            crawler_class = subs_crawler.CRAWLERS[crawler_id]
        except KeyError:
            raise ValueError(f"Invalid crawler id '{crawler_id}")
        parser_id = plan_config["parser"]["name"]
        try:
            parser_class = subs_crawler.PARSERS[parser_id]
        except KeyError:
            raise ValueError(f"Invalid parser id '{parser_id}'")
        crawler_options = plan_config["crawler"].get("options", {})
        parser_options = plan_config["parser"].get("options", {})
        template_options = plan_config.get("template_options", {})
        crawler = crawler_class(None,  # last_version_id will be set in SubstitutionPlan.set_db
                                parser_class, parser_options, **crawler_options)
        plan = SubstitutionPlan(
            plan_id,
            crawler,
            partial(render_template, "substitution-plan.min.html", plan_id=plan_id, subs_options=template_options))

        update_subs = get_update_subs_func(app, plan)
        for cron_time in plan_config.get("background_updates", []):
            aiocron.crontab(cron_time, func=update_subs)

        app.add_subapp(f"/{plan_id}/",
                       plan.create_app(os.path.abspath("assets/static/" + plan_id) if settings.DEBUG else None))

        app["substitution_plans"][plan_id] = plan

    async def root_handler(request: web.Request):
        location = f"/{settings.DEFAULT_PLAN_ID}/"
        if request.query_string:
            location += "?" + request.query_string
        raise web.HTTPPermanentRedirect(location=location)

    app.add_routes([
        web.get("/", root_handler),
        web.get("/privacy", redirect_handler("/about")),
        web.get("/about", template_handler("about.min.html", render_args=dict(about_html=settings.ABOUT_HTML))),
        web.get("/plausible", template_handler("plausible.min.html", {"X-Robots-Tag": "noindex"}))
    ])

    if settings.DEBUG:
        async def test500_handler(request: web.Request):
            if "log" in request.query:
                _LOGGER.error("Test error")
            raise ValueError
        app.add_routes([web.get("/test500", test500_handler)])

        app.router.add_static("/", "assets/static/")

    app.cleanup_ctx.extend((client_session_context, databases_context))

    return app


def main():
    web.run_app(app_factory(f"Starting server on "
                            f"{settings.PATH if settings.PATH else str(settings.HOST) + ':' + str(settings.PORT)}"
                            f"{' (DEBUG MODE)' if settings.DEBUG else ''}"),
                path=settings.PATH, host=settings.HOST, port=settings.PORT, print=_LOGGER.info)


if __name__ == "__main__":
    main()
