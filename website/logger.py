import asyncio
import contextvars
import logging
import logging.handlers
import secrets
import sys
import time
from typing import Union, Optional

import aiohttp
from aiohttp import web

from settings import settings

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
_tg_bot_handler: Optional["TelegramBotLogHandler"] = None

# disable aiohttp.access logger
logging.getLogger("aiohttp.access").propagate = False


class TelegramBotLogHandler(logging.Handler):
    def __init__(self, client_session: aiohttp.ClientSession, level: Union[int, str], token: str, chat_id: Union[int, str]):
        super().__init__(level)
        self._client_session = client_session
        self._url = f"https://api.telegram.org/bot{token}/sendMessage"
        self._chat_id = chat_id

    def emit(self, record: logging.LogRecord) -> None:
        """ Important note: Expects logging call to be made from an event loop. """
        if not self._client_session.closed:
            loop = asyncio.get_running_loop()

            async def r():
                if not self._client_session.closed:
                    data = {"text": self.format(record), "chat_id": self._chat_id, "entities": []}
                    if settings.TELEGRAM_BOT_LOGGER_USE_FIXED_WIDTH:
                        msg = data["text"].replace("<", "&lt").replace(">", "&gt;").replace("&", "&amp;")
                        if "\n" in msg:
                            msg = "<pre>" + msg + "</pre>"
                        else:
                            msg = "<code>" + msg + "</code>"
                        data["text"] = msg
                        data["parse_mode"] = "HTML"
                    await self._client_session.post(self._url, data=data)
            loop.create_task(r())

    async def cleanup(self):
        await self._client_session.close()


async def init(filepath):
    file_handler = logging.handlers.WatchedFileHandler(filepath, encoding="utf-8")
    file_handler.setFormatter(_log_formatter)
    _root.addHandler(file_handler)
    if settings.TELEGRAM_BOT_LOGGER_TOKEN:
        global _tg_bot_handler
        _tg_bot_handler = TelegramBotLogHandler(aiohttp.ClientSession(), settings.TELEGRAM_BOT_LOGGER_LEVEL,
                                                settings.TELEGRAM_BOT_LOGGER_TOKEN,
                                                settings.TELEGRAM_BOT_LOGGER_CHAT_ID)
        _tg_bot_handler.setFormatter(_log_formatter)
        _root.addHandler(_tg_bot_handler)

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
        else:
            if req_id:
                record.msg = f"[] [{req_id}] {record.msg}"
        return record

    logging.setLogRecordFactory(factory)


async def cleanup():
    await _tg_bot_handler.cleanup()


def get_logger():
    return _logger


def request_wrapper(request_handler):
    async def wrapper(self, request: web.Request) -> web.Response:
        PLAN_NAME_CONTEXTVAR.set(self._plan_id)
        return await request_handler(self, request)
    return wrapper


@web.middleware
async def logging_middleware(request: web.Request, handler):
    REQUEST_ID_CONTEXTVAR.set(secrets.token_hex(4))
    _logger.info(f"{request.method} {request.path_qs}")
    t1 = time.perf_counter_ns()
    response: web.Response = await handler(request)
    _logger.info(f"Response status={response.status}, "
                 f"{'length=' + str(response.content_length) + ', ' if response.content_length else ''}"
                 f"time={time.perf_counter_ns()-t1}ns")
    return response
