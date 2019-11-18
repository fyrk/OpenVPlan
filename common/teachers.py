from common.base import BaseSelectionHandler


class TeacherSelectionHandler(BaseSelectionHandler):
    @staticmethod
    def parse(text):
        return text
    
    @staticmethod
    def parse_db(text):
        return text
    
    @staticmethod
    def write_db(text):
        return text
