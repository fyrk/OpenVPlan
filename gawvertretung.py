#!/usr/bin/env python3.8
# -*- coding: utf-8 -*-
import asyncio
import datetime
import os
import pickle
import time
import urllib.error
import urllib.parse
import urllib.request

import aiohttp

from logging_tool import create_logger
from substitution_plan.loader import StudentSubstitutionLoader, TeacherSubstitutionLoader
from substitution_plan.parser import get_status_string
from substitution_plan.utils import parse_class_selection
from website.api import SubstitutionAPI
from website.stats import Stats
from website.templates import Templates

os.chdir(os.path.abspath(os.path.dirname(__file__)))


class SubstitutionPlan:
    URL_STUDENTS = "https://gaw-verden.de/images/vertretung/klassen/subst_{:03}.htm"
    URL_TEACHERS = "https://gaw-verden.de/images/vertretung/lehrer/subst_{:03}.htm"

    URL_FIRST_SITE = URL_STUDENTS.format(1)

    FILENAME_SUBSTITUTIONS = "data/substitutions/substitutions.pickle"
    SUBSTITUTIONS_VERSION = 2
    PATH_STATS = "data/stats/"

    def __init__(self):
        self.stats = Stats(self.PATH_STATS)
        self.substitution_loader_students = StudentSubstitutionLoader("klassen", self.URL_STUDENTS, self.stats)
        self.substitution_loader_teachers = TeacherSubstitutionLoader("lehrer", self.URL_TEACHERS)
        self.api = SubstitutionAPI(self)
        self.templates = Templates()

        self.current_status_date = datetime.datetime.now().date()

        self.current_status_string = ""
        self.data_students = []
        self.data_teachers = []
        self.index_site_students = ""
        self.index_site_teachers = ""

    async def async_init(self):
        await self.templates.load_static()
        await self._try_load_substitutions_from_file()

    async def _try_load_substitutions_from_file(self):
        # noinspection PyBroadException
        try:
            with open(self.FILENAME_SUBSTITUTIONS, "rb") as f:
                version = int.from_bytes(f.read(1), "big", signed=False)
                if version == self.SUBSTITUTIONS_VERSION:
                    self.current_status_string, self.data_students, self.data_teachers = pickle.load(f)
                else:
                    logger.warn(f"substitutions file saved in wrong version: {version} "
                                f"(required: {self.SUBSTITUTIONS_VERSION})")
        except Exception:
            logger.exception("Could not load substitutions from file")
        else:
            logger.info(f"Loaded substitutions from file, status is {repr(self.current_status_string)}")
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
        async with aiohttp.ClientSession() as session:
            logger.info("Loading new data...")
            t1 = time.perf_counter_ns()
            self.data_students, self.data_teachers = await asyncio.gather(
                self.substitution_loader_students.load_data(session, first_site),
                self.substitution_loader_teachers.load_data(session)
            )
            t2 = time.perf_counter_ns()
            logger.debug(f"New data created in {t2 - t1}ns")

    async def update_data(self):
        logger.debug("Requesting subst_001.htm ...")
        t1 = time.perf_counter_ns()
        with urllib.request.urlopen(self.URL_FIRST_SITE) as site:
            text = site.read()
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
        today = datetime.datetime.now().date()
        if today > self.current_status_date:
            self.current_status_date = today
            if not status_changed:
                logger.debug("Date changed, recreating sites")
                await self._create_sites()

    async def _create_sites(self):
        t1 = time.perf_counter_ns()
        self.index_site_students, self.index_site_teachers = await asyncio.gather(
            self.templates.render_substitution_plan_students(self.current_status_string, self.data_students),
            self.templates.render_substitution_plan_teachers(self.current_status_string, self.data_teachers)
        )
        t2 = time.perf_counter_ns()
        logger.debug(f"Index sites created in {t2 - t1}ns")

    async def get_site_students(self, storage):
        # noinspection PyBroadException
        try:
            await self.update_data()
            if "s" in storage:
                classes, selection = parse_class_selection(storage["s"][0].strip())
                if selection:
                    return "200 OK", await self.templates.render_substitution_plan_students(self.current_status_string,
                                                                                            self.data_students,
                                                                                            selection,
                                                                                            ", ".join(classes))
            return "200 OK", self.index_site_students
        except Exception:
            logger.exception("Exception occurred")
            return "500 Internal Server Error", self.templates.error_500_students

    async def get_site_teachers(self, storage):
        # noinspection PyBroadException
        try:
            await self.update_data()
            if "s" in storage:
                selection = storage["s"][0]
                if selection:
                    return "200 OK", await self.templates.render_substitution_plan_teachers(self.current_status_string,
                                                                                            self.data_teachers,
                                                                                            selection.lower(),
                                                                                            selection.upper())
            return "200 OK", self.index_site_teachers
        except Exception:
            logger.exception("Exception occurred")
            return "500 Internal Server Error", self.templates.error_500_teachers

    async def get_current_status(self):
        # noinspection PyBroadException
        try:
            await self.update_data()
            return "200 OK", self.current_status_string
        except Exception:
            logger.exception("Exception occurred")
            return "500 Internal Server Error", ""


logger = create_logger("website")

substitution_plan = SubstitutionPlan()
asyncio.run(substitution_plan.async_init())


def application(environ, start_response):
    try:
        substitution_plan.stats.new_request(environ)
        if environ["PATH_INFO"].startswith("/api"):
            return substitution_plan.api.application(environ["PATH_INFO"][4:], environ, start_response)

        t1 = time.perf_counter_ns()
        if environ["REQUEST_METHOD"] == "GET":
            if environ["PATH_INFO"] == "/":
                logger.info("GET /")
                storage = urllib.parse.parse_qs(environ["QUERY_STRING"])
                response, content = asyncio.run(substitution_plan.get_site_students(storage))
            elif environ["PATH_INFO"] == "/teachers":
                logger.info("GET /teachers")
                storage = urllib.parse.parse_qs(environ["QUERY_STRING"])
                response, content = asyncio.run(substitution_plan.get_site_teachers(storage))
            elif environ["PATH_INFO"] == "/privacy":
                logger.info("GET /privacy")
                response = "200 OK"
                content = substitution_plan.templates.privacy
            elif environ["PATH_INFO"] == "/about":
                logger.info("GET /about")
                response = "200 OK"
                content = substitution_plan.templates.about
            else:
                response = "404 Not Found"
                content = substitution_plan.templates.error_404
            content = content.encode("utf-8")
            t2 = time.perf_counter_ns()
            logger.debug(f"Time for handling request: {t2 - t1}ns")
            start_response(response, [("Content-Type", "text/html;charset=utf-8"),
                                      ("Content-Length", str(len(content)))])
            return [content]

        if environ["REQUEST_METHOD"] == "POST" and environ["PATH_INFO"] == "/":
            logger.info("POST /")
            response, content = asyncio.run(substitution_plan.get_current_status())
            content = content.encode("utf-8")
            t2 = time.perf_counter_ns()
            logger.debug(f"Time for handling request: {t2 - t1}ns")
            start_response(response, [("Content-Type", "text/text;charset=utf-8"),
                                      ("Content-Length", str(len(content)))])
            return [content]

        if environ["REQUEST_METHOD"] == "HEAD":
            if environ["PATH_INFO"] == "/":
                logger.info("HEAD /")
                storage = urllib.parse.parse_qs(environ["QUERY_STRING"])
                response, content = asyncio.run(substitution_plan.get_site_students(storage))
            elif environ["PATH_INFO"] == "/teachers":
                logger.info("HEAD /teachers")
                storage = urllib.parse.parse_qs(environ["QUERY_STRING"])
                response, content = asyncio.run(substitution_plan.get_site_teachers(storage))
            else:
                raise ValueError(f"gawvertretung.py shouldn't be called for path '{environ['PATH_INFO']}'")

            content = content.encode("utf-8")
            t2 = time.perf_counter_ns()
            logger.debug(f"Time for handling request: {t2 - t1}ns")
            start_response(response, [("Content-Type", "text/html;charset=utf-8"),
                                      ("Content-Length", str(len(content)))])
            return []

        content = "Error: 405 Method Not Allowed".encode("utf-8")
        substitution_plan.stats.new_method_not_allowed(environ)
        start_response("405 Method Not Allowed", [("Content-Type", "text/text;charset=utf-8"),
                                                  ("Content-Length", str(len(content)))])
        return [content]
    finally:
        substitution_plan.stats.save()
