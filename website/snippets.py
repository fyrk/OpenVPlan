import os


class Snippets:
    def __init__(self, path):
        self.__files = {}
        for filename in list(os.walk(path))[0][2]:
            if filename.count(".") == 1:
                file, ext = filename.split(".")
                if ext == "html":
                    with open(path + filename, "r") as f:
                        self.__files[file] = f.read()

    def get(self, name):
        try:
            return self.__files[name]
        except KeyError:
            raise ValueError("Did not find snippet '{}'".format(name))
