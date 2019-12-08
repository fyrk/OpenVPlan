from common.teachers import TeacherSubstitution, TeacherSubstitutionGroup
from common.utils import split_class_name
from website.snippets import Snippets
from website.stats import Stats
from .substitution_plan_base import BaseHTMLCreator, BaseSubstitutionParser, BaseSubstitutionLoader


class TeacherSubstitutionParser(BaseSubstitutionParser):
    def __init__(self, data: dict, current_timestamp: int):
        super().__init__(data, current_timestamp)
        self.is_in_strike = False
        self.current_strikes = []

    def get_current_group(self):
        return (self.current_substitution[0], self.current_strikes[0])

    def get_current_substitution(self):
        class_name = self.current_substitution[2]
        if "," in class_name:
            if class_name.startswith("(") and class_name.endswith(")"):
                has_brackets = True
                class_name = class_name[1:-1]
            else:
                has_brackets = False
            classes = [split_class_name(name.strip()) for name in class_name.split(",")]
            if classes[0][0] and all(classes[0][0] == class_[0] for class_ in classes):
                class_name = classes[0][0] + "".join(class_[1] for class_ in classes)
                if has_brackets:
                    class_name = "(" + class_name + ")"
        is_teacher_striked = self.current_strikes[3]
        self.current_strikes = []
        return TeacherSubstitution(
            self.current_substitution[1],
            class_name,
            self.current_substitution[3],
            self.current_substitution[4],
            self.current_substitution[5],
            self.current_substitution[6],
            self.current_substitution[7],
            is_teacher_striked
        )

    def handle_starttag(self, tag, attrs):
        super().handle_starttag(tag, attrs)
        if tag == "strike":
            self.is_in_strike = True

    def handle_endtag(self, tag):
        super().handle_endtag(tag)
        if tag == "strike":
            self.is_in_strike = False

    def handle_data_mon_list(self, data):
        if self.is_in_tag_td:
            self.current_strikes.append(self.is_in_strike)
            self.current_substitution.append(data)


class TeacherSubstitutionLoader(BaseSubstitutionLoader):
    def __init__(self, url: str, stats: Stats = None):
        super().__init__(TeacherSubstitutionParser, url, stats)

    def _sort_substitutions(self, substitutions: dict):
        return sorted(TeacherSubstitutionGroup(group_name, substitutions)
                      for group_name, substitutions in substitutions.items())


class TeacherHTMLCreator(BaseHTMLCreator):
    def __init__(self, snippets: Snippets):
        super().__init__(snippets,
                         "substitution-plan-teachers",
                         "substitution-table-teachers",
                         "notice-teacher-is-selected",
                         "no-substitutions-reset-teachers",
                         "select-teacher")

    def is_selected(self, group, processed_selection):
        return group[0].lower() == processed_selection

    def parse_selection(self, teacher_name: str):
        stripped = teacher_name.strip()
        return stripped.lower(), stripped