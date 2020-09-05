import contextvars
import logging
import logging.handlers
import secrets
import sys
from typing import Callable, Awaitable

from aiohttp import web

_logger = logging.getLogger("gawvertretung")

PLAN_NAME_CONTEXTVAR = contextvars.ContextVar("plan_name")
REQUEST_ID_CONTEXTVAR = contextvars.ContextVar("request_id")

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
        plan_name = PLAN_NAME_CONTEXTVAR.get(None)
        req_id = REQUEST_ID_CONTEXTVAR.get(None)
        if plan_name:
            if req_id:
                record.msg = f"[{plan_name}] [{req_id}] {record.msg}"
            else:
                record.msg = f"[{plan_name}] {record.msg}"
        return record

    logging.setLogRecordFactory(factory)


def get_logger():
    return _logger


def request_wrapper(request_handler):
    async def wrapper(self, request: web.Request) -> web.Response:
        req_id = secrets.token_hex(4)
        req_token = REQUEST_ID_CONTEXTVAR.set(req_id)
        pname_token = PLAN_NAME_CONTEXTVAR.set(self._name)
        try:
            response = await request_handler(self, request)
            return response
        finally:
            REQUEST_ID_CONTEXTVAR.reset(req_token)
            PLAN_NAME_CONTEXTVAR.reset(pname_token)
    return wrapper


@web.middleware
async def logging_middleware(request: web.Request, handler):
    response: web.Response = await handler(request)
    _logger.info(f"{request.method} {request.path} {response.status}")
    return response
