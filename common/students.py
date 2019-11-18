from common.base import BaseSelectionHandler


class StudentSelectionHandler(BaseSelectionHandler):
    @staticmethod
    def parse(text):
        selected_classes = []
        for selected_class in "".join(text.split()).split(","):
            if selected_class and selected_class not in selected_classes:
                selected_classes.append(selected_class)
        return selected_classes
    
    @staticmethod
    def parse_db(text):
        return text.split(",")
    
    @staticmethod
    def write_db(selection):
        return ",".join(selection)
