import contextvars
import datetime
import logging
import os
import secrets
import sys

from argparse import ArgumentParser
import time

import jinja2
from aiohttp import client, http, hdrs, web

from substitution_plan.loader import StudentSubstitutionLoader, TeacherSubstitutionLoader
from website.stats import Stats
from website.substitution_plan import SubstitutionPlan


__version__ = "3.0"

URL_STUDENTS = "https://gaw-verden.de/images/vertretung/klassen/subst_{:03}.htm"
URL_TEACHERS = "https://gaw-verden.de/images/vertretung/lehrer/subst_{:03}.htm"
REQUEST_USER_AGENT = "GaWVertretungBot/" + __version__ + " (+https://gawvertretung.florian-raediker.de) " + \
                     http.SERVER_SOFTWARE
REQUEST_HEADERS = {hdrs.USER_AGENT: REQUEST_USER_AGENT}

WORKING_DIR = os.path.abspath(os.path.dirname(__file__))

root_logger = logging.getLogger()
root_logger.setLevel(logging.DEBUG)

logger = logging.getLogger("gawvertretung")
logger.setLevel(logging.DEBUG)


def init_logger(filename):
    log_formatter = logging.Formatter("{asctime} [{levelname:^8}]: {message}", style="{")
    file_logger = logging.FileHandler(filename, encoding="utf-8")
    file_logger.setFormatter(log_formatter)
    root_logger.addHandler(file_logger)
    stdout_logger = logging.StreamHandler(sys.stdout)
    stdout_logger.setLevel(logging.ERROR)
    stdout_logger.setFormatter(log_formatter)
    root_logger.addHandler(stdout_logger)


TEMPLATES_PATH = os.path.join(WORKING_DIR, "website/templates")
TEMPLATES_CACHE_PATH = os.path.join(WORKING_DIR, "data/template_cache/")
STATIC_PATH = os.path.join(WORKING_DIR, "website/static/")
STATS_PATH = os.path.join(WORKING_DIR, "data/stats/")
LOGS_PATH = os.path.join(WORKING_DIR, "logs/")


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
        logger.info(f'{request.method} {request.path} {response.status} {response.body_length} '
                    f'{time.perf_counter_ns()-t1}ns "{request.headers.get(hdrs.USER_AGENT, "-")}"')
        return response
    finally:
        request_id_contextvar.reset(token)


@web.middleware
async def stats_middleware(request: web.Request, handler):
    response: web.Response = await handler(request)
    if not response.prepared:
        try:
            await response.prepare(request)
            await response.write_eof()
        except:
            logger.exception("Exception for " + repr(request))
    await stats.new_request(request, response)
    return response


@web.middleware
async def error_middleware(request: web.Request, handler):
    # noinspection PyBroadException
    try:
        return await handler(request)
    except web.HTTPException as e:
        if e.status == 404:
            return web.Response(text=await TEMPLATE_ERROR404.render_async(), content_type="text/html", charset="utf-8")
    except Exception:
        logger.exception(f"{request.method} {request.path} Exception while handling request")
    return web.Response(text=await TEMPLATE_ERROR500_STUDENTS.render_async(), content_type="text/html", charset="utf-8")


class TemplateHandler:
    def __init__(self, template: jinja2.Template):
        self._template = template

    async def __call__(self, request: web.Request) -> web.Response:
        return web.Response(text=await self._template.render_async(), content_type="text/html")


async def client_session(app: web.Application):
    logger.debug("Create ClientSession")
    app["client_session"] = client.ClientSession(headers=REQUEST_HEADERS)
    yield
    await app["client_session"].close()


async def app_factory(host, port, dev_mode=False):
    app = web.Application(middlewares=[logging_middleware, stats_middleware, error_middleware])
    logger.info(f"Starting server on {host}:{port}{' in dev mode' if dev_mode else ''}")
    loader_students = StudentSubstitutionLoader(URL_STUDENTS, "students")
    loader_students.on_status_changed = stats.add_last_site
    plan_students = SubstitutionPlan(loader_students, TEMPLATE_STUDENTS, TEMPLATE_ERROR500_STUDENTS)
    loader_teachers = TeacherSubstitutionLoader(URL_TEACHERS, "teachers")
    loader_teachers.on_status_changed = stats.add_last_site
    plan_teachers = SubstitutionPlan(loader_teachers, TEMPLATE_TEACHERS, TEMPLATE_ERROR500_TEACHERS)

    app.add_routes([
        web.get("/", plan_students.handler),
        web.get("/teachers", plan_teachers.handler),

        web.get("/api/students/wait-for-update", plan_students.wait_for_update_handler),
        web.get("/api/teachers/wait-for-update", plan_teachers.wait_for_update_handler),

        web.get("/privacy", TemplateHandler(TEMPLATE_PRIVACY)),
        web.get("/about", TemplateHandler(TEMPLATE_ABOUT))
    ])

    if dev_mode:
        app.router.add_static("/", STATIC_PATH)

    app.cleanup_ctx.append(client_session)

    return app


def run(host, port, dev_mode=False):
    web.run_app(app_factory(host, port, dev_mode), host=host, port=port)


if __name__ == "__main__":
    arg_parser = ArgumentParser(
        description="gawvertretung server"
    )
    arg_parser.add_argument(
        "-D", "--dev",
        action="store_true",
        help="Run server in dev mode (static files served, outdated substitutions included, ...)"
    )
    arg_parser.add_argument(
        "-L", "--log",
        help="Logfile name (saved in 'logs' folder), website-<current date>.log by default",
        default=datetime.datetime.now().strftime("website-%Y-%m-%d.log")
    )
    arg_parser.add_argument(
        "-W", "--working-dir",
        help="Working directory",
        default=WORKING_DIR
    )
    arg_parser.add_argument(
        "-H", "--hostname",
        help="TCP/IP hostname to serve on (default: %(default)r)",
        default="localhost"
    )
    arg_parser.add_argument(
        "-P", "--port",
        help="TCP/IP port to serve on (default: %(default)r)",
        type=int,
        default="8080"
    )
    args = arg_parser.parse_args()
    WORKING_DIR = args.working_dir
    if args.dev:
        from substitution_plan import parser
        parser.INCLUDE_OUTDATED_SUBSTITUTIONS = True
    init_logger(os.path.join(LOGS_PATH, args.log))
    run(args.hostname, args.port, args.dev)
