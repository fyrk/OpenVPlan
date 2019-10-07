#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import time
import logging
import urllib.parse
from http.server import HTTPServer, SimpleHTTPRequestHandler

import gawvertretung


class HTTPRequestHandler(SimpleHTTPRequestHandler):
    def do_GET(self):
        try:
            parsed_url = urllib.parse.urlparse(self.path)
            storage = urllib.parse.parse_qs(parsed_url.query)
            gawvertretung.logger.info("Request: {} with params {}".format(parsed_url.path, storage))
            if parsed_url.path == "/":
                t1 = time.perf_counter()
                content = gawvertretung.get_main_page(storage)
                t2 = time.perf_counter()
                gawvertretung.logger.info("Time for handling request: {:.3f}".format(t2 - t1))
                content_type = "text/html"
            elif parsed_url.path == "/api/last-status":
                gawvertretung.get_main_page(storage)
                content = gawvertretung.status_string
                content_type = "text/text"
            else:
                self.path = "/static" + self.path
                return super().do_GET()
        except Exception:
            gawvertretung.logger.exception("Could not handle request")
            content = gawvertretung.Snippets.ERROR
            content_type = "text/html"
        self.send_response(200)
        bytes_data = content.encode("utf-8")
        self.send_header("Content-type", content_type + ";charset=utf-8")
        self.send_header("Content-length", str(len(bytes_data)))
        self.end_headers()
        self.wfile.write(bytes_data)


if __name__ == "__main__":
    gawvertretung.logger.info("Starting server...")
    httpd = HTTPServer(('0.0.0.0', 8001), HTTPRequestHandler)
    gawvertretung.logger.info("Server started")
    try:
        httpd.serve_forever()
    finally:
        httpd.shutdown()
        logging.shutdown()
        gawvertretung.logger.error("Error occurred, shutting down")
