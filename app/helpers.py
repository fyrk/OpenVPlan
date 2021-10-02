#  OpenVPlan
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

import yarl
from aiohttp import web


def static_url(app: web.Application, static_file_path: str, cache_busting: bool = True) -> str:
    if cache_busting:
        if static_file_path in (cb := app["cache_busting"]):
            static_file_path += "?v=" + cb[static_file_path]
        else:
            app["logger"].warning(f"Missing cache busting parameter for '{static_file_path}'")
    # if static files are served by aiohttp-devtools from localhost:8001
    """"# copied from aiohttp_jinja2.helpers:
    try:
        static_url = app["static_root_url"]
    except KeyError:
        raise RuntimeError(
            "app does not define a static root url "
            "'static_root_url', you need to set the url root "
            "with app['static_root_url'] = '<static root>'."
        ) from None
    return static_url.rstrip("/") + "/" + static_file_path.lstrip("/")"""
    return "/" + static_file_path.lstrip("/")


async def render_template(name: str, app: web.Application, **kwargs):
    settings = app["settings"]
    if app["settings"].debug or app["cache_busting"] is None:  # always reload cache_busting.json in debug mode
        with open(app["cache_busting_path"], "r") as f:
            app["cache_busting"] = json.load(f)
    ferien = settings.enable_ferien
    if ferien and settings.ferien_start and settings.ferien_end and \
            not (settings.ferien_start < datetime.datetime.now() < settings.ferien_end):
        ferien = False
    return await app["jinja2_env"].get_template(name).render_async(
        static=lambda path,cb=True: static_url(app, path, cb), plausible=settings.plausible, ferien=ferien, news=settings.news, 
        options=settings.template_options,
        **kwargs)


@web.middleware
async def error_middleware(request: web.Request, handler):
    settings = request.app["settings"]
    logger = request.app["logger"]
    # noinspection PyBroadException
    try:
        return await handler(request)
    except web.HTTPException as e:
        if e.status == 404:
            return web.Response(text=await render_template("error-404.min.html", request.app),
                                status=404, content_type="text/html", charset="utf-8",
                                headers=request.app["response_headers"])
        raise
    except asyncio.CancelledError:
        raise
    except Exception:
        logger.exception(f"{request.method} {request.path} Exception while handling request")
    except BaseException:
        logger.exception(f"{request.method} {request.path} BaseException while handling request")
        raise
    plan_id = request.get("plan_id")
    # noinspection PyBroadException
    try:
        original_data_link = settings.substitution_plans[plan_id]["template_options"]["original_data_link"]
    except Exception:
        original_data_link = \
            settings.substitution_plans[settings.default_plan_id]["template_options"]["original_data_link"]
    return web.Response(text=await render_template("error-500.min.html", request.app, plan_id=plan_id,
                                                   original_data_link=original_data_link),
                        status=500, content_type="text/html", charset="utf-8", headers=request.app["response_headers"])


def get_template_handler(app: web.Application, name: str, response_headers: dict = None, render_args: dict = None):
    if not render_args:
        render_args = {}

    async def handler(request: web.Request):
        if response_headers:
            headers = {**app["response_headers"], **response_headers}
        else:
            headers = app["response_headers"]
        response = web.Response(text=await render_template(name, app, **render_args),
                                content_type="text/html", headers=headers)
        return response
    return handler


def redirect_handler(location, **kwargs):
    async def handler(r):
        raise web.HTTPMovedPermanently(location, **kwargs)
    return handler


def set_response_headers(app: web.Application):
    settings = app["settings"]
    csp = {
        "default-src": "'none'",
        "style-src": ["'self'"],
        "manifest-src": ["'self'"],
        "img-src": ["'self'", "data:"],
        "script-src": [
            "'self'",
            "'sha256-VXAFuXMdnSA19vGcFOCPVOnWUq6Dq5vRnaGtNp0nH8g='",  # const a=localStorage.getItem("dark-theme") ...
            "'sha256-3/1ODIQTRjv+w06gdm2GcdfvbXBk8D893PBaImH3siQ='",  # document.getElementById("view-e") ...
            "'sha256-DxdO0KMifr4qBxX++GTv0w7cNu8FeArRvitEZf1FSrE='",
            # window.plausible=window.plausible||function() ...
            "'sha256-bfloDFhW9eAYHv7CGM+kIiD7H2F+b/hGF5Wj8LOnLyo='",
            # plausible("404",{props:{path:document.location ...
            "'sha256-MUo3BR9SqVxUnxV7Dw9uvwDu81yLUU2qKuLSqkGuXmE='",
            # plausible("500",{props:{path:document.location ...
        ],
        "connect-src": ["'self'", "ws:" if settings.debug else "wss:"],
        "frame-src": ["'self'", "mailto:"],
        "object-src": ["'self'", "mailto:"]
    }

    if settings.debug:
        csp["script-src"].append("http://localhost:8001/livereload.js")
        # if static files are served by aiohttp-devtools from localhost:8001
        """# aiohttp-devtools serves assets from localhost:8001
        static_root_url = yarl.URL(str(app["static_root_url"]))
        if static_root_url.host:
            static_host = static_root_url.host
            if static_root_url.port:
                static_host += ":" + str(static_root_url.port)
            csp["style-src"].append(static_host)
            csp["img-src"].append(static_host)
            csp["script-src"].append(static_host)"""

    if (plausible := settings.plausible) and plausible.get("domain") and (plausible_js := plausible.get("js")):
        csp["script-src"].append(plausible_js)
        csp["connect-src"].append(plausible.get("endpoint") or
                                  (str(yarl.URL(plausible_js).origin())+"/api/event"))
    for name, value in settings.additional_csp_directives.items():
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

    headers = {
        "Content-Security-Policy": csp_header,
        "Strict-Transport-Security": "max-age=63072000",
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1",
        "X-Robots-Tag": "noarchive, notranslate"
    }
    if settings.headers_block_floc:
        headers["Permissions-Policy"] = "interest-cohort=()"

    app["response_headers"] = headers
