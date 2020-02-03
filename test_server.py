# https://docs.python.org/3/library/wsgiref.html#examples
import mimetypes
import os
import sys
from wsgiref import simple_server, util

import gawvertretung


path_website_static = sys.argv[1] if len(sys.argv) > 1 else os.path.join(os.getcwd(), "website/static/")
path_node_modules = "."


def application_wrapper(environ, respond):
    if environ["PATH_INFO"].startswith(gawvertretung.BASE_PATH):
        environ["PATH_INFO"] = environ["PATH_INFO"][len(gawvertretung.BASE_PATH):]
    for fn in (os.path.join(path_website_static, environ['PATH_INFO'][1:]), os.path.join(path_node_modules, environ['PATH_INFO'][1:])):
        if '.' not in fn.split(os.path.sep)[-1]:
            fn = os.path.join(fn, 'index.html')
        type = mimetypes.guess_type(fn)[0]
        if os.path.exists(fn):
            respond('200 OK', [('Content-Type', type)] if type is not None else [])
            return util.FileWrapper(open(fn, "rb"))
    return gawvertretung.application(environ, respond)


if __name__ == '__main__':
    port = int(sys.argv[2]) if len(sys.argv) > 2 else 8000
    httpd = simple_server.make_server('', port, application_wrapper)
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        httpd.server_close()
