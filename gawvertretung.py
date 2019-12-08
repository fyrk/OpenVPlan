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

from common.utils import get_status_string
from logging_tool import create_logger
from website.snippets import Snippets
from website.stats import Stats
from website.substitution_plan_students import StudentHTMLCreator, StudentSubstitutionLoader
from website.substitution_plan_teachers import TeacherHTMLCreator, TeacherSubstitutionLoader

os.chdir(os.path.abspath(os.path.dirname(__file__)))


class SubstitutionPlan:
    URL_STUDENTS = "https://gaw-verden.de/images/vertretung/klassen/subst_{:03}.htm"
    URL_TEACHERS = "https://gaw-verden.de/images/vertretung/lehrer/subst_{:03}.htm"

    URL_FIRST_SITE = URL_STUDENTS.format(1)

    FILENAME_SUBSTITUTIONS = "data/substitutions/substitutions.pickle"
    FILENAME_STATS = "data/stats.json"

    PATH_SNIPPETS = "website/snippets/"

    def __init__(self, logger):
        self.stats = Stats(self.FILENAME_STATS)
        self.logger = logger
        self.substitution_loader_students = StudentSubstitutionLoader(self.URL_STUDENTS, self.stats)
        self.substitution_loader_teachers = TeacherSubstitutionLoader(self.URL_TEACHERS)
        self.snippets = Snippets(self.PATH_SNIPPETS)
        self.html_creator_students = StudentHTMLCreator(self.snippets)
        self.html_creator_teachers = TeacherHTMLCreator(self.snippets)

        self.current_status_date = datetime.datetime.now().date()

        try:
            with open(self.FILENAME_SUBSTITUTIONS, "rb") as f:
                self.current_status_string, self.data_students, self.data_teachers = pickle.load(f)
        except Exception:
            self.logger.error("Could not load substitutions from file")
        else:
            logger.info(f"Loaded substitutions from file (status is '{self.current_status_string}')")
            self.index_site_students = self.html_creator_students.create_html(self.data_students,
                                                                              self.current_status_string)
            self.index_site_teachers = self.html_creator_teachers.create_html(self.data_teachers,
                                                                              self.current_status_string)
            return

        self.current_status_string = ""
        self.data_students = []
        self.data_teachers = []
        self.index_site_students = ""
        self.index_site_teachers = ""

    async def _load_data(self, first_site):
        logger.debug("Creating new data...")
        t1 = time.perf_counter()
        self.data_students, self.data_teachers = await asyncio.gather(
            self.substitution_loader_students.load_data("klassen", first_site),
            self.substitution_loader_teachers.load_data("lehrer")
        )
        t2 = time.perf_counter()
        self.logger.debug(f"New data created in {t2 - t1:.3f} {self.data_students}")

    def update_data(self):
        self.logger.debug("Requesting subst_001.htm ...")
        t1 = time.perf_counter()
        with urllib.request.urlopen(self.URL_FIRST_SITE) as site:
            text = site.read()
        t2 = time.perf_counter()
        new_status_string = get_status_string(text)
        self.logger.debug(f"Got answer in {t2 - t1:.3f}: {new_status_string}")
        self.logger.debug(f"Old status is {self.current_status_string}")
        status_changed = False
        if new_status_string != self.current_status_string:
            # status changed, load new data
            status_changed = True
            self.current_status_string = new_status_string
            self.stats.add_status(self.current_status_string)
            asyncio.run(self._load_data(text))
            self._create_sites()
            self.send_substitutions_to_bot()
            self.stats.save()
        today = datetime.datetime.now().date()
        if today > self.current_status_date:
            self.current_status_date = today
            if not status_changed:
                self.logger.debug("Date changed, recreating sites")
                self._create_sites()

    def send_substitutions_to_bot(self):
        with open(self.FILENAME_SUBSTITUTIONS, "wb") as f:
            pickle.dump((
                self.current_status_string,
                self.data_students,
                self.data_teachers
            ), f)
        logger.info("Wrote substitutions to file")

    def _create_sites(self):
        t1 = time.perf_counter()
        self.index_site_students = self.html_creator_students.create_html(self.data_students,
                                                                          self.current_status_string)
        self.index_site_teachers = self.html_creator_teachers.create_html(self.data_teachers,
                                                                          self.current_status_string)
        t2 = time.perf_counter()
        self.logger.debug("Sites created in {:.3f}".format(t2 - t1))

    def get_site_students(self, storage):
        # noinspection PyBroadException
        try:
            self.update_data()
            if "classes" in storage:
                selection = storage["classes"][0]
                if selection:
                    return "200 OK", self.html_creator_students.create_html(self.data_students,
                                                                            self.current_status_string,
                                                                            selection)
            return "200 OK", self.index_site_students
        except Exception:
            logger.exception("Exception occurred")
            return "500 Internal Server Error", self.snippets.get("error-500-students")

    def get_site_teachers(self, storage):
        # noinspection PyBroadException
        try:
            self.update_data()
            if "teacher" in storage:
                selection = storage["teacher"][0]
                if selection:
                    return "200 OK", self.html_creator_teachers.create_html(self.data_teachers,
                                                                            self.current_status_string,
                                                                            selection)
            return "200 OK", self.index_site_teachers
        except Exception:
            logger.exception("Exception occurred")
            return "500 Internal Server Error", self.snippets.get("error-500-teachers")

    def get_current_status(self):
        # noinspection PyBroadException
        try:
            self.update_data()
            return "200 OK", self.current_status_string
        except Exception:
            logger.exception("Exception occurred")
            return "500 Internal Server Error", ""


logger = create_logger("website")

substitution_plan = SubstitutionPlan(logger)


def application(environ, start_response):
    t1 = time.perf_counter()
    if environ["REQUEST_METHOD"] == "GET":
        if environ["PATH_INFO"] == "/":
            logger.info("GET /")
            storage = urllib.parse.parse_qs(environ["QUERY_STRING"])
            response, content = substitution_plan.get_site_students(storage)
            content = content.encode("utf-8")
            t2 = time.perf_counter()
            logger.debug(f"Time for handling request: {t2 - t1}")
            start_response(response, [("Content-Type", "text/html;charset=utf-8"),
                                      ("Content-Length", str(len(content)))])
            return [content]

        if environ["PATH_INFO"] == "/teachers":
            logger.info("GET /teachers")
            storage = urllib.parse.parse_qs(environ["QUERY_STRING"])
            response, content = substitution_plan.get_site_teachers(storage)
            content = content.encode("utf-8")
            t2 = time.perf_counter()
            logger.debug(f"Time for handling request: {t2 - t1}")
            start_response(response, [("Content-Type", "text/html;charset=utf-8"),
                                      ("Content-Length", str(len(content)))])
            return [content]

        t2 = time.perf_counter()
        logger.debug(f"Time for handling request: {t2 - t1}")
        content = substitution_plan.snippets.get("error-404").encode("utf-8")
        start_response("404 Not Found", [("Content-Type", "text/html;charset=utf-8"),
                                         ("Content-Length", str(len(content)))])
        return [content]

    if environ["REQUEST_METHOD"] == "POST" and environ["PATH_INFO"] == "/":
        logger.info("POST /")
        response, content = substitution_plan.get_current_status()
        content = content.encode("utf-8")
        t2 = time.perf_counter()
        logger.debug(f"Time for handling request: {t2 - t1}")
        start_response(response, [("Content-Type", "text/text;charset=utf-8"),
                                  ("Content-Length", str(len(content)))])
        return [content]

    content = "Error: 405 Method Not Allowed".encode("utf-8")
    start_response("405	Method Not Allowed", [("Content-Type", "text/text;charset=utf-8"),
                                                 ("Content-Length", str(len(content)))])
    return [content]
