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

import os
from functools import partial
from pathlib import Path

import jinja2
from aiohttp import client, hdrs
from aiojobs.aiohttp import setup as aiojobs_setup

from . import log_helper
from . import subs_crawler
from .db import SubstitutionPlanDB
from .helpers import *
from .settings import Settings
from .substitution_plan import SubstitutionPlan

THIS_DIR = Path(__file__).parent

DATA_DIR = "/var/lib/gawvertretung"
CACHE_DIR = "/var/cache/gawvertretung"

for directory in (
    DATA_DIR,
    CACHE_DIR
):
    os.makedirs(directory, exist_ok=True)


BACKGROUND_UPDATES = [
    # min     hour dom mon dow sec
    "  0       *    *   *   *   R",  # every hour all the time
    "15,30,45 5-22  *   *  1-5  R",  # all 15 minutes from 5-22 o'clock on weekdays
    "46-59     6    *   *  1-5  R",  # every minute on weekdays from 6:46 to 6:59
    "1-14,16-29,31-44,46-59 7 * * 1-5 R"  # every minute on weekdays from 7:01 to 7:59
]


async def db_context(app):
    app["db"] = SubstitutionPlanDB(os.path.join(DATA_DIR, "db.sqlite3"))
    subs_plan: SubstitutionPlan
    for subs_plan in app["substitution_plans"].values():
        subs_plan.on_db_init(app)
    yield
    app["db"].close()


async def client_session_context(app):
    request_headers = app["settings"].request_headers
    app["logger"].debug(f"Create ClientSession (headers: {request_headers})")
    app["client_session"] = client.ClientSession(headers=request_headers)
    yield
    await app["client_session"].close()


async def response_headers_startup(app):
    # call this here so that aiohttp-devtools has already modified app["static_root_url"]
    set_response_headers(app)


async def subapp_startup(app):
    for subapp in app["subapps"]:
        for key in ("settings", "logger", "cache_busting_path", "db", "client_session", "jinja2_env",
                    "response_headers", "AIOJOBS_SCHEDULER"):
            # noinspection PyTypedDict
            subapp[key] = app[key]


async def fix_aiohttp_devtools_bug(app):
    # fix a bug in aiohttp_devtools/runserver/serve.py modify_main_app():
    # Content-Length is not modified after livereload.js is injected
    # see also: https://github.com/aio-libs/aiohttp-devtools/pull/289
    async def on_prepare(request, response):
        if (not request.path.startswith('/_debugtoolbar') and
                'text/html' in response.content_type and
                getattr(response, 'body', False)):
            response.headers[hdrs.CONTENT_LENGTH] = str(len(response.body))

    app.on_response_prepare.append(on_prepare)


async def cleanup(app):
    app["logger"].info("Shutting down...")
    for subs_plan in app["substitution_plans"].values():
        await subs_plan.cleanup()
    await log_helper.cleanup()


async def create_app():
    app = web.Application(middlewares=[log_helper.logging_middleware, error_middleware])

    settings = Settings()

    app["settings"] = settings

    await log_helper.init(app)
    logger_ = log_helper.get_logger()

    if not settings.substitution_plans:
        raise ValueError("No substitution_plans defined")

    if settings.debug:
        logger_.info("RUNNING IN DEBUG MODE")

    static_path = str(THIS_DIR / "../static")

    env = jinja2.Environment(
        loader=jinja2.FileSystemLoader(str(THIS_DIR / "templates")),
        bytecode_cache=jinja2.FileSystemBytecodeCache(os.path.join(CACHE_DIR)),
        enable_async=True,
        autoescape=True,
        trim_blocks=True,
        lstrip_blocks=True,
        auto_reload=settings.debug
    )

    app.update(
        cache_busting_path=str(THIS_DIR / "templates/cache_busting.json"),
        logger=logger_,
        jinja2_env=env,
        substitution_plans={},
        cache_busting=None,
    )

    aiojobs_setup(app)

    app.cleanup_ctx.extend([
        db_context,
        client_session_context
    ])

    app.on_startup.append(response_headers_startup)

    app.on_startup.append(subapp_startup)

    app.on_cleanup.append(cleanup)

    if settings.debug:
        app.on_startup.append(fix_aiohttp_devtools_bug)

    app["subapps"] = []

    for plan_id, plan_config in settings.substitution_plans.items():
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
            partial(render_template, "substitution-plan.min.html",
                    app=app, plan_id=plan_id, subs_options=template_options))

        subapp = plan.create_app(BACKGROUND_UPDATES, static_path+"/"+plan_id if settings.debug else None)
        app["subapps"].append(subapp)
        app.add_subapp(f"/{plan_id}/", subapp)

        app["substitution_plans"][plan_id] = plan

    async def root_handler(request: web.Request):
        location = f"/{settings.default_plan_id}/"
        if request.query_string:
            location += "?" + request.query_string
        raise web.HTTPPermanentRedirect(location=location)

    app.add_routes([
        web.get("/", root_handler),
        web.get("/privacy", redirect_handler("/about")),
        web.get("/about", get_template_handler(app, "about.min.html",
                                               render_args=dict(about_html=settings.about_html))),
        web.get("/plausible", get_template_handler(app, "plausible.min.html",
                                                   {"X-Robots-Tag": "noindex"}))
    ])

    if settings.debug:
        async def test500_handler(request: web.Request):
            if "log" in request.query:
                app["logger"].error("Test error")
            raise ValueError
        app.add_routes([web.get("/test500", test500_handler)])

        app.add_routes([
            # for source files referenced in sourcemaps:
            web.static("/node_modules", str(THIS_DIR.parent / "node_modules")),
            web.static("/static_src", str(THIS_DIR.parent / "static_src")),

            web.static("/", static_path)
        ])

        print("SOURCES", static_path, str(THIS_DIR.parent))

    app["logger"].info("Server initialized")

    return app


if __name__ == "__main__":
    web.run_app(create_app(), host="0.0.0.0", port=8000)