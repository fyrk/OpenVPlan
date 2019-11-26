#!/usr/local/bin/python3
# -*- coding: utf-8 -*-
import logging
import os.path
import sys
import urllib.parse
from http.server import HTTPServer, SimpleHTTPRequestHandler

sys.path.append(os.path.dirname(__file__))
import gawvertretung


class HTTPRequestHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        self.handle_request("GET")

    def handle_request(self, method):
        try:
            parsed_url = urllib.parse.urlparse(self.path)
            environ = {"REQUEST_METHOD": method, "PATH_INFO": parsed_url.path, "QUERY_STRING": parsed_url.query}
            for key, value in self.headers.items():
                environ["HTTP_" + key] = value
            if self.path.startswith("/js") or self.path.startswith("/style") or self.path.startswith("/img") or \
                    self.path.startswith("/manifest.json") or self.path.startswith("/favicon"):
                self.path = "/website/static" + self.path
                return super().do_GET()
            self.wfile.write(gawvertretung.application(environ, self.start_response)[0])
        except Exception:
            self.start_response("500 ERROR", [("Content-Type", "text/text; charset=utf-8")])
            self.wfile.write("Es ist ein Fehler aufgetreten".encode("utf-8"))

    def do_POST(self):
        self.handle_request("POST")

    def start_response(self, code_and_message, headers):
        code, message = code_and_message.split(" ", 1)
        code = int(code)
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
