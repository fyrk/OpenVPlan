import contextvars
import logging
import os
import secrets
import sys
import time

import atexit
import jinja2
from aiohttp import client, http, hdrs, web
from aiohttp.web_fileresponse import FileResponse

from gawvertretung import config
from gawvertretung.substitution_plan.loader import StudentSubstitutionLoader, TeacherSubstitutionLoader
from gawvertretung.website.stats import Stats
from gawvertretung.website.substitution_plan import SubstitutionPlan


__version__ = "3.0"

URL_STUDENTS = config.get_str("url_students")
URL_TEACHERS = config.get_str("url_teachers")
REQUEST_USER_AGENT = config.get_str("user_agent", "GaWVertretungBot").format(version=__version__,
                                                                             server_software=http.SERVER_SOFTWARE)
REQUEST_HEADERS = {hdrs.USER_AGENT: REQUEST_USER_AGENT}

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


TEMPLATES_PATH = os.path.join(WORKING_DIR, "gawvertretung/website/templates")
TEMPLATES_CACHE_PATH = os.path.join(WORKING_DIR, "data/template_cache/")
STATIC_PATH = os.path.join(WORKING_DIR, "gawvertretung/website/static/")
STATS_PATH = os.path.join(WORKING_DIR, "data/stats/")


stats = Stats(STATS_PATH)

env = jinja2.Environment(
    loader=jinja2.FileSystemLoader(TEMPLATES_PATH),
    bytecode_cache=jinja2.FileSystemBytecodeCache(TEMPLATES_CACHE_PATH),
    autoescape=jinja2.select_autoescape(["html"]),
    enable_async=True,
    trim_blocks=True,
    lstrip_blocks=True)
TEMPLATE_STUDENTS = env.get_template("substitution-plan-students.min.html")
TEMPLATE_TEACHERS = env.get_template("substitution-plan-teachers.min.html")
TEMPLATE_PRIVACY = env.get_template("privacy.min.html")
TEMPLATE_ABOUT = env.get_template("about.min.html")
TEMPLATE_ERROR404 = env.get_template("error-404.html")
TEMPLATE_ERROR500_STUDENTS = env.get_template("error-500-students.html")
TEMPLATE_ERROR500_TEACHERS = env.get_template("error-500-teachers.html")

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
    t1 = time.perf_counter_ns()
    req_id = secrets.token_hex(4)
    request["request_id"] = req_id
    token = request_id_contextvar.set(req_id)
    try:
        response: web.Response = await handler(request)
        try:
            user_agent = '"' + request.headers[hdrs.USER_AGENT].replace('"', '\"') + '"'
        except KeyError:
            user_agent = "-"
        _LOGGER.info(f"{request.method} {request.path} {response.status} {response.body_length} "
                     f"{time.perf_counter_ns()-t1}ns {user_agent}")
        return response
    finally:
        request_id_contextvar.reset(token)


@web.middleware
async def stats_middleware(request: web.Request, handler):
    response: web.Response = await handler(request)
    if not response.prepared and type(response) != FileResponse:
        # noinspection PyBroadException
        try:
            await response.prepare(request)
            await response.write_eof()
        except Exception:
            _LOGGER.exception("Exception occurred while preparing and writing response")
    await stats.new_request(request, response)
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
        _LOGGER.exception(f"{request.method} {request.path} HTTPException while handling request")
    except Exception:
        _LOGGER.exception(f"{request.method} {request.path} Exception while handling request")
    return web.Response(text=await TEMPLATE_ERROR500_STUDENTS.render_async(), status=500, content_type="text/html",
                        charset="utf-8")


def template_handler(template: jinja2.Template):
    # noinspection PyUnusedLocal
    async def handler(request: web.Request):
        return web.Response(text=await template.render_async(), content_type="text/html")
    return handler


async def client_session(app: web.Application):
    _LOGGER.debug("Create ClientSession")
    app["client_session"] = client.ClientSession(headers=REQUEST_HEADERS)
    yield
    await app["client_session"].close()


async def app_factory(host, port, dev_mode=False):
    app = web.Application(middlewares=[logging_middleware, stats_middleware, error_middleware])
    _LOGGER.info(f"Starting server on {host}:{port}{' in dev mode' if dev_mode else ''}")

    loader_students = StudentSubstitutionLoader(URL_STUDENTS, "students")
    loader_students.on_status_changed = stats.add_last_site
    plan_students = SubstitutionPlan(loader_students, TEMPLATE_STUDENTS, TEMPLATE_ERROR500_STUDENTS)
    plan_students.deserialize("data/substitutions/students.pickle")

    loader_teachers = TeacherSubstitutionLoader(URL_TEACHERS, "teachers")
    loader_teachers.on_status_changed = stats.add_last_site
    plan_teachers = SubstitutionPlan(loader_teachers, TEMPLATE_TEACHERS, TEMPLATE_ERROR500_TEACHERS)
    plan_teachers.deserialize("data/substitutions/teachers.pickle")

    def serialize_substitutions():
        plan_students.serialize("data/substitutions/students.pickle")
        plan_teachers.serialize("data/substitutions/teachers.pickle")

    atexit.register(serialize_substitutions)

    app.add_routes([
        web.get("/", plan_students.handler),
        web.get("/teachers", plan_teachers.handler),

        web.get("/api/students/wait-for-update", plan_students.wait_for_update_handler),
        web.get("/api/teachers/wait-for-update", plan_teachers.wait_for_update_handler),

        web.get("/privacy", template_handler(TEMPLATE_PRIVACY)),
        web.get("/about", template_handler(TEMPLATE_ABOUT))
    ])

    if dev_mode:
        app.router.add_static("/", STATIC_PATH)

    app.cleanup_ctx.append(client_session)

    return app


def run(host, port, dev_mode=False):
    web.run_app(app_factory(host, port, dev_mode), host=host, port=port)


if __name__ == "__main__":
    init_logger(os.path.join(WORKING_DIR, config.get_str("logfile", "logs/website.log")))
    run(config.get_str("host", "localhost"), config.get_int("port", 8080), config.get_bool("dev"))
