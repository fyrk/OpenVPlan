import os
import string


class Snippets:
    def __init__(self, path):
        self.__files = {}
        for filename in list(os.walk(path))[0][2]:
            if filename.count(".") == 1:
                file, ext = filename.split(".")
                if ext == "html":
                    with open(path + filename, "r") as f:
                        self.__files[file] = string.Template(f.read())

    def get(self, name, **formatting):
        try:
            return self.__files[name].substitute(**formatting)
        except KeyError:
            raise ValueError("Did not find snippet '{}'".format(name))
