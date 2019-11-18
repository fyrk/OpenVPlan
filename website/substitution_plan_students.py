from collections import OrderedDict
from functools import lru_cache

from .substitution_plan_base import BaseHTMLCreator, BaseSubstitutionParser, BaseSubstitutionLoader, BaseSubstitution
from .substitution_utils import sort_classes, split_class_name_lower


class StudentSubstitution(BaseSubstitution):
    def __init__(self, teacher, substitute, lesson, subject, room, subs_from, hint):
        super().__init__(lesson)
        self.teacher = teacher
        self.substitute = substitute
        self.subject = subject
        self.room = room
        self.subs_from = subs_from
        self.hint = hint

    @lru_cache()
    def get_html_first_of_group(self, group_substitution_count, group_name, snippets, add_lesson_num):
        return snippets.get("substitution-row-first-students").format(
            group_substitution_count,
            group_name,
            self.teacher,
            self.substitute,
            self.lesson,
            self.subject,
            self.room,
            self.subs_from,
            self.hint,
            lesson_num=self.lesson_num if add_lesson_num else ""
        )

    @lru_cache()
    def get_html(self, snippets, add_lesson_num):
        return snippets.get("substitution-row-students").format(
            self.teacher,
            self.substitute,
            self.lesson,
            self.subject,
            self.room,
            self.subs_from,
            self.hint,
            lesson_num=self.lesson_num if add_lesson_num else ""
        )


class StudentSubstitutionParser(BaseSubstitutionParser):
    def __init__(self, data, current_timestamp):
        super().__init__(data, current_timestamp)

    def get_current_group(self):
        return self.current_substitution[0]

    def get_current_substitution(self):
        return StudentSubstitution(*self.current_substitution[1:])


class StudentSubstitutionLoader(BaseSubstitutionLoader):
    def __init__(self, url):
        super().__init__(StudentSubstitutionParser, url)

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
        selected_classes = []
        for selected_class in "".join(selection.split()).split(","):
            if selected_class not in selected_classes:
                selected_classes.append(selected_class)
        print(selected_classes)
        return [split_class_name_lower(name) for name in selected_classes], ", ".join(selected_classes)

    def is_selected(self, class_name, processed_selection):
        print("check class", repr(class_name), processed_selection)
        class_name = class_name.lower()
        if class_name == "" or class_name == "\xa0":  # "\xa0" is non-breaking space
            # class_name is empty, check if empty class name is in selection
            return ("", "") in processed_selection
        return any((selected_class[0] in class_name and selected_class[1] in class_name)
                   for selected_class in processed_selection if selected_class[0] or selected_class[1])
