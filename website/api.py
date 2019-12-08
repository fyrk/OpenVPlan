import datetime
import json
import urllib.parse

from common.students import parse_selection, split_class_name_lower
from common.utils import create_date_timestamp


class SubstitutionAPI:
    def __init__(self, substitution_plan):
        self.substitution_plan = substitution_plan

    def application(self, path, environ, start_response):
        def handle_error(response, description=None):
            data = {"ok": False, "error": response}
            if description:
                data["message"] = description
            content = json.dumps(data).encode("utf-8")
            start_response(response, [("Content-Type", "application/json;charset=utf-8"),
                                      ("Content-Length", str(len(content)))])
            return [content]

        # noinspection PyBroadException
        try:
            if path != "/classes" and path != "/teachers":
                return handle_error("404 Not Found")

            # parse request data
            if environ["REQUEST_METHOD"] == "GET":
                request_data = {}
                for key, value in urllib.parse.parse_qs(environ["QUERY_STRING"]).items():
                    if len(value) == 1:
                        request_data[key] = value[0]
                    else:
                        return handle_error("400 Bad Request", f"You must specify only one value per parameter, but "
                                                               f"multiple values were given for '{key}'")
            elif environ["REQUEST_METHOD"] == "POST":
                try:
                    request_data = json.loads(environ["wsgi.input"].read(int(environ["CONTENT_LENGTH"])))
                except json.decoder.JSONDecodeError:
                    return handle_error("400 Bad Request", "Could not parse JSON")
            else:
                return handle_error("405 Method Not Allowed")

            self.substitution_plan.update_data()
            current_timestamp = create_date_timestamp(datetime.datetime.now())
            if path == "/classes":
                if "selection" in request_data:
                    selection = [split_class_name_lower(c) for c in parse_selection(request_data["selection"])]
                else:
                    selection = None
                data = {"ok": True, "days": [d.to_dict(selection) for d in self.substitution_plan.data_students
                                             if d.timestamp >= current_timestamp]}
            else:
                assert path == "/teachers"
                if "selection" in request_data:
                    selection = request_data["selection"].strip().upper()
                else:
                    selection = None
                data = {"ok": True, "days": [d.to_dict(selection) for d in self.substitution_plan.data_teachers
                                             if d.timestamp >= current_timestamp]}
            pretty = "pretty" in request_data and (request_data["pretty"] == "True" or request_data["pretty"] == "true")
            content = json.dumps(data, indent=4 if pretty else None).encode("utf-8")
            start_response("200 OK", [("Content-Type", "application/json;charset=utf-8"),
                                      ("Content-Length", str(len(content)))])
            return [content]
        except Exception:
            self.substitution_plan.logger.exeption("API: Exception occurred")
            return handle_error("500 Internal Server Error")
