#!/usr/bin/env python3.8
# -*- coding: utf-8 -*-

__version__ = "2.0"

import asyncio
import atexit
import datetime
import logging
import os
import pickle
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import List

import aiohttp

from substitution_plan.loader import StudentSubstitutionLoader, TeacherSubstitutionLoader
from substitution_plan.parser import get_status_string
from substitution_plan.storage import SubstitutionDay
from substitution_plan.utils import split_selection, create_date_timestamp
from website.api import SubstitutionAPI
from website.stats import Stats
from website.templates import Templates

WORKING_DIR = os.path.abspath(os.path.dirname(__file__))

LOG_FILE = os.path.join(WORKING_DIR, datetime.datetime.now().strftime("logs/website-%Y-%m-%d.log"))

logger = logging.getLogger()
logger.handlers.clear()
logger.setLevel(logging.DEBUG)
log_formatter = logging.Formatter("{threadName}:{thread} {asctime} [{levelname:^8}]: {message}", style="{")
file_logger = logging.FileHandler(LOG_FILE, encoding="utf-8")
file_logger.setFormatter(log_formatter)
logger.addHandler(file_logger)
stdout_logger = logging.StreamHandler(sys.stdout)
stdout_logger.setLevel(logging.ERROR)
stdout_logger.setFormatter(log_formatter)
logger.addHandler(stdout_logger)

logger.info("Started gawvertretung.py with working directory '" + WORKING_DIR + "'")

BASE_PATH = ""  # leave empty for production


class SubstitutionPlan:
    URL_STUDENTS = "https://gaw-verden.de/images/vertretung/klassen/subst_{:03}.htm"
    URL_TEACHERS = "https://gaw-verden.de/images/vertretung/lehrer/subst_{:03}.htm"
    URL_FIRST_SITE = URL_STUDENTS.format(1)

    FILENAME_SUBSTITUTIONS = os.path.join(WORKING_DIR, "data/substitutions/substitutions.pickle")
    SUBSTITUTIONS_VERSION = 2
    PATH_STATS = os.path.join(WORKING_DIR, "data/stats/")
    TEMPLATE_DIR = os.path.join(WORKING_DIR, "website/templates/")
    TEMPLATE_CACHE_DIR = os.path.join(WORKING_DIR, "data/template_cache/")

    AIOHTTP_USER_AGENT = "GaWVertretungBot/" + __version__ + " (+https://gawvertretung.florian-raediker.de) " + \
                         aiohttp.http.SERVER_SOFTWARE
    AIOHTTP_HEADERS = {aiohttp.hdrs.USER_AGENT: AIOHTTP_USER_AGENT}

    stats: Stats
    substitution_loader_students: StudentSubstitutionLoader
    substitution_loader_teachers: TeacherSubstitutionLoader
    api: SubstitutionAPI
    templates: Templates
    current_status_date: datetime.date
    current_status_date: str
    data_students: List[SubstitutionDay]
    data_teachers: List[SubstitutionDay]
    index_site_students: bytes
    index_site_teachers: bytes
    loop: asyncio.AbstractEventLoop
    aiohttp_session: aiohttp.ClientSession

    def __init__(self):
        self.stats = Stats(self.PATH_STATS)
        self.api = SubstitutionAPI(self)
        self.templates = Templates(self.TEMPLATE_DIR, self.TEMPLATE_CACHE_DIR, BASE_PATH)

        self.current_status_date = datetime.datetime.now().date()

        self.current_status_string = ""
        self.data_students = []
        self.data_teachers = []
        self.index_site_students = b""
        self.index_site_teachers = b""

        self.loop = asyncio.get_event_loop()

        async def async_init():
            await self._try_load_substitutions_from_file()
            self.aiohttp_session = aiohttp.ClientSession(headers=self.AIOHTTP_HEADERS)
            self.substitution_loader_students = StudentSubstitutionLoader(self.aiohttp_session, "klassen",
                                                                          self.URL_STUDENTS, self.stats)
            self.substitution_loader_teachers = TeacherSubstitutionLoader(self.aiohttp_session, "lehrer",
                                                                          self.URL_TEACHERS)
        self.loop.run_until_complete(async_init())

    def close(self):
        async def _before_exit():
            logger.info("Shutting down")
            logger.debug("Saving stats")
            self.stats.save()
            logger.debug("Closing aiohttp session")
            await self.aiohttp_session.close()
        self.loop.run_until_complete(_before_exit())

    async def _try_load_substitutions_from_file(self):
        # noinspection PyBroadException
        try:
            with open(self.FILENAME_SUBSTITUTIONS, "rb") as f:
                version = int.from_bytes(f.read(1), "big", signed=False)
                if version == self.SUBSTITUTIONS_VERSION:
                    self.current_status_string, self.data_students, self.data_teachers = pickle.load(f)
                else:
                    raise ValueError(f"substitutions file saved in wrong version: {version} "
                                     f"(required: {self.SUBSTITUTIONS_VERSION})")
        except Exception:
            logger.exception("Could not load substitutions from file")
        else:
            logger.info(f"Loaded substitutions from file, status is {repr(self.current_status_string)}")
            self._remove_old_days(create_date_timestamp(datetime.datetime.now()))
            await self._create_sites()

    def _save_substitutions(self):
        with open(self.FILENAME_SUBSTITUTIONS, "wb") as f:
            f.write(self.SUBSTITUTIONS_VERSION.to_bytes(1, "big", signed=False))
            pickle.dump((
                self.current_status_string,
                self.data_students,
                self.data_teachers
            ), f)
        logger.info("Wrote substitutions to file")

    async def _load_data(self, first_site: bytes):
        logger.info("Loading new data...")
        t1 = time.perf_counter_ns()
        self.data_students, self.data_teachers = await asyncio.gather(
            self.substitution_loader_students.load_data(
                {d.timestamp: d.get_substitution_sets() for d in self.data_students}, first_site),
            self.substitution_loader_teachers.load_data(
                {d.timestamp: d.get_substitution_sets() for d in self.data_teachers})
        )
        t2 = time.perf_counter_ns()
        logger.debug(f"New data created in {t2 - t1}ns")

    async def update_data(self):
        logger.debug("Requesting subst_001.htm ...")
        t1 = time.perf_counter_ns()
        async with self.aiohttp_session.get(self.URL_FIRST_SITE) as r:
            text = await r.read()
        t2 = time.perf_counter_ns()
        new_status_string = get_status_string(text)
        logger.debug(f"Got answer in {t2 - t1}ns, status is {repr(new_status_string)}, "
                     f"old: {repr(self.current_status_string)}")
        status_changed = False
        if new_status_string != self.current_status_string:
            # status changed, load new data
            status_changed = True
            self.current_status_string = new_status_string
            self.stats.add_status(self.current_status_string)
            await self._load_data(text)
            await self._create_sites()
            self._save_substitutions()
        today = datetime.datetime.now()
        today_date = today.date()
        if today_date > self.current_status_date:
            self.current_status_date = today_date
            if not status_changed:
                logger.debug("Date changed, recreating sites")
                self._remove_old_days(create_date_timestamp(today))
                await self._create_sites()

    def _remove_old_days(self, current_timestamp):
        while len(self.data_students) and self.data_students[0].timestamp < current_timestamp:
            del self.data_students[0]
            del self.data_teachers[0]

    async def _create_sites(self):
        t1 = time.perf_counter_ns()
        index_students, index_teachers = await asyncio.gather(
            self.templates.render_substitution_plan_students(self.current_status_string, self.data_students),
            self.templates.render_substitution_plan_teachers(self.current_status_string, self.data_teachers)
        )
        self.index_site_students = index_students.encode("utf-8")
        self.index_site_teachers = index_teachers.encode("utf-8")
        t2 = time.perf_counter_ns()
        logger.debug(f"Index sites created in {t2 - t1}ns")

    async def application_students(self, environ, start_response):
        # noinspection PyBroadException
        try:
            await self.update_data()
            storage = urllib.parse.parse_qs(environ["QUERY_STRING"])
            if "s" in storage:
                selection = split_selection(",".join(storage["s"]))
                if selection:
                    content = (await self.templates.render_substitution_plan_students(
                        self.current_status_string, self.data_students,
                        [s.upper() for s in selection], ", ".join(selection))).encode("utf-8")
                    start_response("200 OK", [("Content-Type", "text/html;charset=utf-8"),
                                              ("Content-Length", str(len(content))),
                                              ("X-Robots-Tag", "noindex")])
                    return [content]
            start_response("200 OK", [("Content-Type", "text/html;charset=utf-8"),
                                      ("Content-Length", str(len(self.index_site_students))),
                                      ("X-Robots-Tag", "noarchive, notranslate")])
            return [self.index_site_students]
        except Exception:
            logger.exception("Exception occurred")
            content = (await self.templates.render_error_500_students()).encode("utf-8")
            start_response("500 Internal Server Error", [("Content-Type", "text/html;charset=utf-8"),
                                                         ("Content-Length", str(len(content))),
                                                         ("X-Robots-Tag", "noarchive, notranslate")])
            return [content]

    async def application_teachers(self, environ, start_response):
        # noinspection PyBroadException
        try:
            await self.update_data()
            storage = urllib.parse.parse_qs(environ["QUERY_STRING"])
            if "s" in storage:
                selection = sorted(split_selection(",".join(storage["s"])))
                if selection:
                    content = (await self.templates.render_substitution_plan_teachers(
                        self.current_status_string, self.data_teachers, [
                            s.upper() for s in selection], ", ".join(selection).upper())).encode("utf-8")
                    start_response("200 OK", [("Content-Type", "text/html;charset=utf-8"),
                                              ("Content-Length", str(len(content))),
                                              ("X-Robots-Tag", "noindex")])
                    return [content]
            start_response("200 OK", [("Content-Type", "text/html;charset=utf-8"),
                                      ("Content-Length", str(len(self.index_site_teachers))),
                                      ("X-Robots-Tag", "noarchive, notranslate")])
            return [self.index_site_teachers]
        except Exception:
            logger.exception("Exception occurred")
            content = (await self.templates.render_error_500_teachers()).encode("utf-8")
            start_response("500 Internal Server Error", [("Content-Type", "text/html;charset=utf-8"),
                                                         ("Content-Length", str(len(content))),
                                                         ("X-Robots-Tag", "noarchive, notranslate")])
            return [content]

    async def application_post(self, environ, start_response):
        response, content = asyncio.run(self.get_current_status())
        content = content.encode("utf-8")
        start_response(response, [("Content-Type", "text/text;charset=utf-8"),
                                  ("Content-Length", str(len(content)))])
        return [content]

    async def get_current_status(self):
        # noinspection PyBroadException
        try:
            await self.update_data()
            return "200 OK", self.current_status_string
        except Exception:
            logger.exception("Exception occurred")
            return "500 Internal Server Error", ""

    async def async_application(self, environ, start_response):
        t1 = time.perf_counter_ns()
        try:
            self.stats.new_request(environ)
            METHOD = environ["REQUEST_METHOD"]
            PATH = environ["PATH_INFO"]
            logger.info(METHOD + " " + PATH)
            if PATH.startswith("/api"):
                return await self.api.application(PATH[4:], environ, start_response)

            IS_GET = METHOD == "GET"
            IS_HEAD = METHOD == "HEAD"
            if IS_GET or IS_HEAD:
                if PATH == "/":
                    content = await self.application_students(environ, start_response)
                    if IS_GET:
                        return content
                    return []
                elif PATH == "/teachers":
                    content = await self.application_teachers(environ, start_response)
                    if IS_GET:
                        return content
                    return []
                elif PATH == "/privacy":
                    response = "200 OK"
                    content = await self.templates.render_privacy()
                elif PATH == "/about":
                    response = "200 OK"
                    content = await self.templates.render_about()
                else:
                    self.stats.new_not_found(environ)
                    response = "404 Not Found"
                    content = await self.templates.render_error_404()
                    if IS_HEAD:
                        content = content.encode("utf-8")
                        start_response(response, [("Content-Type", "text/html;charset=utf-8"),
                                                  ("Content-Length", str(len(content)))])
                        return []
            else:
                self.stats.new_method_not_allowed(environ)
                response = "405 Method Not Allowed"
                content = await self.templates.render_error_405(method=METHOD, path=PATH)

            content = content.encode("utf-8")
            start_response(response, [("Content-Type", "text/html;charset=utf-8"),
                                      ("Content-Length", str(len(content)))])
            return [content]
        finally:
            t2 = time.perf_counter_ns()
            logger.debug(f"Time for handling request: {t2 - t1}ns")


substitution_plan = SubstitutionPlan()


def application(environ, start_response):
    return substitution_plan.loop.run_until_complete(substitution_plan.async_application(environ, start_response))


atexit.register(substitution_plan.close)
