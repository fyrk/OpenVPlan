import argparse
import contextvars
import logging
import os
import secrets
import sys
import time

import jinja2
from aiohttp import client, http, hdrs, web
from aiohttp.web_fileresponse import FileResponse

from gawvertretung import config
from gawvertretung.db.db import SubstitutionPlanDBStorage
from gawvertretung.substitution_plan.loader import StudentSubstitutionLoader, TeacherSubstitutionLoader
from gawvertretung.website.stats import Stats
from gawvertretung.website.substitution_plan import SubstitutionPlan


__version__ = "3.0"

WORKING_DIR = os.path.abspath(os.path.dirname(__file__))

_LOGGER = logging.getLogger("gawvertretung")
_LOGGER.setLevel(logging.DEBUG)


def init_logger(filepath):
    log_formatter = logging.Formatter("{asctime} [{levelname:^8}]: {message}", style="{")

    file_logger = logging.FileHandler(filepath, encoding="utf-8")
    file_logger.setFormatter(log_formatter)
    _LOGGER.addHandler(file_logger)

    stdout_logger = logging.StreamHandler(sys.stdout)
    stdout_logger.setLevel(logging.ERROR)
    stdout_logger.setFormatter(log_formatter)
    _LOGGER.addHandler(stdout_logger)


REQUEST_USER_AGENT = config.get_str("user_agent", "GaWVertretungBot").format(version=__version__,
                                                                             server_software=http.SERVER_SOFTWARE)
REQUEST_HEADERS = {hdrs.USER_AGENT: REQUEST_USER_AGENT}


STATIC_PATH = os.path.join(WORKING_DIR, "assets/static/")
STATS_PATH = os.path.join(WORKING_DIR, "data/stats/")


stats = Stats(STATS_PATH)

env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(os.path.join(WORKING_DIR, "assets/templates")),
    bytecode_cache=jinja2.FileSystemBytecodeCache(os.path.join(WORKING_DIR, "data/template_cache/")),
    enable_async=True,
    trim_blocks=True,
    lstrip_blocks=True)
TEMPLATE_PRIVACY = env.get_template("privacy.min.html")
TEMPLATE_ABOUT = env.get_template("about.min.html")
TEMPLATE_ERROR404 = env.get_template(config.get_str("template404"))
TEMPLATE_ERROR500 = env.get_template(config.get_str("template500"))

request_id_contextvar = contextvars.ContextVar("request_id")


def add_logging_factory():
    def new_factory(*args, **kwargs):
        record = old_factory(*args, **kwargs)
        req_id = request_id_contextvar.get(None)
        if req_id:
            record.msg = f"[{req_id}] {record.msg}"
        return record
    old_factory = logging.getLogRecordFactory()
    logging.setLogRecordFactory(new_factory)


add_logging_factory()


@web.middleware
async def logging_middleware(request: web.Request, handler):
    req_id = secrets.token_hex(4)
    request["request_id"] = req_id
    token = request_id_contextvar.set(req_id)
    try:
        response: web.Response = await handler(request)
        _LOGGER.info(f"{request.method} {request.path} {response.status}")
        return response
    finally:
        request_id_contextvar.reset(token)


@web.middleware
async def stats_middleware(request: web.Request, handler):
    t1 = time.perf_counter_ns()
    response: web.Response = await handler(request)
    if not response.prepared:
        if type(response) != FileResponse:
            # noinspection PyBroadException
            try:
                await response.prepare(request)
                await response.write_eof()
            except Exception:
                _LOGGER.exception("Exception occurred while preparing and writing response")
        else:
            if request.path.endswith("js"):
                response.content_type = "text/javascript"
            elif request.path.endswith(".css"):
                response.content_type = "text/css"
    await stats.new_request(request, response, time.perf_counter_ns()-t1)
    return response


@web.middleware
async def error_middleware(request: web.Request, handler):
    # noinspection PyBroadException
    try:
        return await handler(request)
    except web.HTTPException as e:
        if e.status == 404:
            return web.Response(text=await TEMPLATE_ERROR404.render_async(), status=404, content_type="text/html",
                                charset="utf-8")
        raise e from None
    except Exception:
        _LOGGER.exception(f"{request.method} {request.path} Exception while handling request")
    return web.Response(text=await TEMPLATE_ERROR500.render_async(), status=500, content_type="text/html",
                        charset="utf-8")


def template_handler(template: jinja2.Template):
    # noinspection PyUnusedLocal
    async def handler(request: web.Request):
        return web.Response(text=await template.render_async(), content_type="text/html")
    return handler


async def client_session_context(app: web.Application):
    _LOGGER.debug("Create ClientSession")
    session = client.ClientSession(headers=REQUEST_HEADERS)
    for substitution_plan in app["substitution_plans"].values():
        substitution_plan.client_session = session
    yield
    await session.close()


async def databases_context(app: web.Application):
    for substitution_plan in app["substitution_plans"].values():
        storage = SubstitutionPlanDBStorage("data/storage/" + substitution_plan.name + ".sqlite3")
        substitution_plan.storage = storage
    yield
    for substitution_plan in app["substitution_plans"].values():
        substitution_plan.storage.close()


async def app_factory(host, port, dev_mode=False):
    app = web.Application(middlewares=[logging_middleware, stats_middleware, error_middleware])
    _LOGGER.info(f"Starting server on {host}:{port}{' in dev mode' if dev_mode else ''}")

    app["substitution_plans"] = {}
    for name, plan_config in config.get("substitution_plans").items():
        loader_name = plan_config["loader"]
        url = plan_config["url"]
        template_name = plan_config["template"]
        template500_name = plan_config["template500"]
        loader = {"StudentSubstitutionLoader": StudentSubstitutionLoader,
                  "TeacherSubstitutionLoader": TeacherSubstitutionLoader}[loader_name](url, name)
        loader.on_status_changed = stats.add_last_site
        plan = SubstitutionPlan(name, loader, env.get_template(template_name), env.get_template(template500_name))

        await plan.deserialize(f"data/substitutions/{name}.pickle")

        app.add_subapp(f"/{name}/", plan.create_app(os.path.abspath("assets/static/" + name)
                                                    if config.get_bool("dev") else None))

        app["substitution_plans"][name] = plan

    async def root_handler(request: web.Request):
        location = f"/{config.get('default_plan')}/"
        if request.query_string:
            location += "?" + request.query_string
        raise web.HTTPPermanentRedirect(location=location)

    app.add_routes([
        web.get("/", root_handler),
        web.get("/privacy", template_handler(TEMPLATE_PRIVACY)),
        web.get("/about", template_handler(TEMPLATE_ABOUT))
    ])

    if dev_mode:
        app.router.add_static("/", STATIC_PATH)

    app.cleanup_ctx.extend((client_session_context, databases_context))

    return app


def run(path, host, port, dev_mode=False):
    web.run_app(app_factory(host, port, dev_mode), path=path, host=host, port=port)


parser = argparse.ArgumentParser(description="gawvertretung server")
parser.add_argument("--path")
parser.add_argument("--port")

if __name__ == "__main__":
    args = parser.parse_args()
    if args.path:
        path = args.path
        host = None
    else:
        path = None
        host = config.get_str("host", "localhost")
    if args.port:
        port = args.port
    else:
        port = config.get_int("port", 8080)
    init_logger(os.path.join(WORKING_DIR, config.get_str("logfile", "logs/website.log")))
    run(path, host, port, config.get_bool("dev"))
