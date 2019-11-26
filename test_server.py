#!/usr/local/bin/python3
# -*- coding: utf-8 -*-
import logging
import os.path
import sys
import time
import urllib.parse
from http.server import HTTPServer, SimpleHTTPRequestHandler

sys.path.append(os.path.dirname(__file__))
import gawvertretung


class HTTPRequestHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        t1 = time.time()
        try:
            gawvertretung.logger.info("Request: {}".format(self.path))
            environ = {}
            parsed_url = urllib.parse.urlparse(self.path)
            environ["PATH_INFO"] = parsed_url.path
            environ["QUERY_STRING"] = parsed_url.query
            for key, value in self.headers.items():
                environ["HTTP_" + key] = value
            if self.path.startswith("/js") or self.path.startswith("/style") or self.path.startswith("/img") or \
                    self.path.startswith("/manifest.json") or self.path.startswith("/favicon"):
                self.path = "/website/static" + self.path
                return super().do_GET()
            self.wfile.write(gawvertretung.application(environ, self.start_response)[0])
        except Exception:
            gawvertretung.logger.exception("Could not handle request")
            self.start_response("500 ERROR", [("Content-Type", "text/text; charset=utf-8")])
            self.wfile.write(gawvertretung.Snippets.get("error").encode("utf-8"))
        t2 = time.time()
        gawvertretung.logger.info("Time for handling request:" + str(t2-t1))

    def start_response(self, code_and_message, headers):
        code, message = code_and_message.split(" ", 1)
        code = int(code)
        gawvertretung.logger.debug("Response: " + code_and_message)
        self.send_response(code, message)
        for name, value in headers:
            self.send_header(name, value)
        self.end_headers()

    def do_HEAD(self):
        self.path = "/website/static" + self.path
        super().do_HEAD()


if __name__ == "__main__":
    gawvertretung.logger.info("Starting server...")
    httpd = HTTPServer(('0.0.0.0', 8001), HTTPRequestHandler)
    gawvertretung.logger.info("Server started")
    try:
        httpd.serve_forever()
    finally:
        gawvertretung.logger.error("Error occurred, shutting down")
        logging.shutdown()
