import contextvars
import logging
import logging.handlers
import secrets
import sys

from aiohttp import web

_logger = logging.getLogger("gawvertretung")

_plan_name_contextvar = contextvars.ContextVar("plan_name")
_request_id_contextvar = contextvars.ContextVar("request_id")

_root = logging.getLogger()
_root.setLevel(logging.DEBUG)
_log_formatter = logging.Formatter("{asctime} [{levelname:^8}]: {message}", style="{")
_stdout_handler = logging.StreamHandler(sys.stdout)
_stdout_handler.setLevel(logging.ERROR)
_stdout_handler.setFormatter(_log_formatter)
_root.addHandler(_stdout_handler)

# disable aiohttp.access logger
logging.getLogger("aiohttp.access").propagate = False


def init(filepath):
    file_handler = logging.handlers.WatchedFileHandler(filepath, encoding="utf-8")
    file_handler.setFormatter(_log_formatter)
    _root.addHandler(file_handler)

    # Add logging factory so that {message} looks like this instead: "[plan_name] [request_id] {message}"
    old_factory = logging.getLogRecordFactory()

    def factory(name, level, fn, lno, msg, args, exc_info, func=None, sinfo=None, **kwargs):
        record = old_factory(name, level, fn, lno, msg, args, exc_info, func=func, sinfo=sinfo, **kwargs)
        plan_name = _plan_name_contextvar.get("*")
        req_id = _request_id_contextvar.get(None)
        if req_id:
            record.msg = f"[{plan_name}] [{req_id}] {record.msg}"
        return record

    logging.setLogRecordFactory(factory)


def get_logger():
    return _logger


def get_plan_middleware(plan_name: str):
    @web.middleware
    async def logging_middleware(request: web.Request, handler):
        req_id = secrets.token_hex(4)
        req_token = _request_id_contextvar.set(req_id)
        pname_token = _plan_name_contextvar.set(plan_name)
        try:
            return await handler(request)
        finally:
            _request_id_contextvar.reset(req_token)
            _plan_name_contextvar.reset(pname_token)
    return logging_middleware
