from collections import OrderedDict

from common.students import StudentSubstitution, is_class_selected, split_class_name_lower, parse_selection
from website.substitution_utils import sort_classes
from .substitution_plan_base import BaseHTMLCreator, BaseSubstitutionParser, BaseSubstitutionLoader


class StudentSubstitutionParser(BaseSubstitutionParser):
    def __init__(self, data, current_timestamp):
        super().__init__(data, current_timestamp)

    def get_current_group(self):
        return self.current_substitution[0]

    def get_current_substitution(self):
        return StudentSubstitution(*self.current_substitution[1:])


class StudentSubstitutionLoader(BaseSubstitutionLoader):
    def __init__(self, url, stats=None):
        super().__init__(StudentSubstitutionParser, url, stats)

    def _data_postprocessing(self, data):
        for day_timestamp, day in data.items():
            if "absent-teachers" in day:
                day["absent-teachers"] = ", ".join(sorted(day["absent-teachers"].split(", ")))
            if "absent-classes" in day:
                day["absent-classes"] = ", ".join(sorted(day["absent-classes"].split(", "), key=sort_classes))
            day["substitutions"] = OrderedDict(sorted(day["substitutions"].items(), key=lambda s: sort_classes(s[0])))


class StudentHTMLCreator(BaseHTMLCreator):
    def __init__(self, snippets):
        super().__init__(snippets,
                         "substitution-plan-students",
                         "substitution-table-students",
                         "notice-classes-are-selected",
                         "no-substitutions-reset-classes",
                         "select-classes")

    def parse_selection(self, selection):
        selected_classes = parse_selection(selection)
        return [split_class_name_lower(name) for name in selected_classes], ", ".join(selected_classes)

    def is_selected(self, class_name, processed_selection):
        return is_class_selected(class_name, processed_selection)
