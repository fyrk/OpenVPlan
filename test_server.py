#!/usr/local/bin/python3
# -*- coding: utf-8 -*-
import logging
import urllib.parse
from http.server import HTTPServer, SimpleHTTPRequestHandler

import gawvertretung
from logging_tool import create_logger


class HTTPRequestHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        try:
            gawvertretung.logger.info("Request: {}".format(self.path))
            environ = {}
            parsed_url = urllib.parse.urlparse(self.path)
            environ["PATH_INFO"] = parsed_url.path
            environ["QUERY_STRING"] = parsed_url.query
            for key, value in self.headers.items():
                environ["HTTP_" + key] = value
            print("environ", environ)
            if self.path.startswith("/js") or self.path.startswith("/style") or self.path.startswith("/img") or \
                    self.path.startswith("/manifest.json") or self.path.startswith("/favicon"):
                self.path = "/static" + self.path
                return super().do_GET()
            self.wfile.write(gawvertretung.application(environ, self.start_response)[0])
        except Exception:
            gawvertretung.logger.exception("Could not handle request")
            self.start_response("500 ERROR", [("Content-Type", "text/text; charset=utf-8")])
            self.wfile.write(gawvertretung.Snippets.get("error").encode("utf-8"))

    def start_response(self, code_and_message, headers):
        code, message = code_and_message.split(" ", 1)
        code = int(code)
        gawvertretung.logger.debug("Response: " + code_and_message)
        self.send_response(code, message)
        for name, value in headers:
            self.send_header(name, value)
        self.end_headers()

    def do_HEAD(self):
        self.path = "/static" + self.path
        super().do_HEAD()


if __name__ == "__main__":
    gawvertretung.logger = create_logger("website")
    gawvertretung.logger.info("Starting server...")
    httpd = HTTPServer(('0.0.0.0', 8001), HTTPRequestHandler)
    gawvertretung.logger.info("Server started")
    try:
        httpd.serve_forever()
    finally:
        gawvertretung.logger.error("Error occurred, shutting down")
        logging.shutdown()
