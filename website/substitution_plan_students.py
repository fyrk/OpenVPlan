from common.students import StudentSubstitution, split_class_name_lower, parse_selection, StudentSubstitutionGroup
from website.snippets import Snippets
from website.stats import Stats
from .substitution_plan_base import BaseHTMLCreator, BaseSubstitutionParser, BaseSubstitutionLoader


class StudentSubstitutionParser(BaseSubstitutionParser):
    def __init__(self, data: dict, current_timestamp: int):
        super().__init__(data, current_timestamp)

    def get_current_group(self):
        return self.current_substitution[0]

    def get_current_substitution(self):
        return StudentSubstitution(*self.current_substitution[1:])


class StudentSubstitutionLoader(BaseSubstitutionLoader):
    def __init__(self, url: str, stats: Stats = None):
        super().__init__(StudentSubstitutionParser, url, stats)

    def _sort_substitutions(self, substitutions: dict):
        return sorted(StudentSubstitutionGroup(group_name, substitutions)
                      for group_name, substitutions in substitutions.items())


class StudentHTMLCreator(BaseHTMLCreator):
    def __init__(self, snippets: Snippets):
        super().__init__(snippets,
                         "substitution-plan-students",
                         "substitution-table-students",
                         "notice-classes-are-selected",
                         "no-substitutions-reset-classes",
                         "select-classes")

    def parse_selection(self, selection: str):
        selected_classes = parse_selection(selection)
        return [split_class_name_lower(name) for name in selected_classes], ", ".join(selected_classes)
