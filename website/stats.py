import json
import os.path


class Stats:
    def __init__(self, filename):
        if os.path.exists(filename):
            self.data = {"statuses": [], "last-sites": []}
            with open(filename, "r") as f:
                self.data.update(json.load(f))
        else:
            self.data = {"statuses": [], "last-sites": []}
        self.filename = filename
        self.status_was_new = True

    def add_status(self, status):
        if status not in self.data["statuses"]:
            self.data["statuses"].append(status)
            self.status_was_new = True
        else:
            self.status_was_new = False

    def add_last_site(self, site_num):
        if self.status_was_new:
            self.data["last-sites"].append(site_num)

    def save(self):
        with open(self.filename, "w") as f:
            json.dump(self.data, f, indent=4)
