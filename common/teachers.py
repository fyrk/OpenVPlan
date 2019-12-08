import hashlib
from functools import lru_cache

from common.base import BaseSubstitution, BaseSubstitutionGroup


class TeacherSubstitutionGroup(BaseSubstitutionGroup):
    def __lt__(self, other):
        return self.group_name < other.group_name

    def is_selected(self, parsed_selection):
        return self.group_name[0] == parsed_selection


class TeacherSubstitution(BaseSubstitution):
    def __init__(self, lesson, class_name, teacher, subject, room, subs_from, hint, is_substitute_striked):
        super().__init__(lesson)
        self.class_name = class_name
        self.teacher = teacher
        self.subject = subject
        self.room = room
        self.subs_from = subs_from
        self.hint = hint
        self.is_substitute_striked = is_substitute_striked

    def __repr__(self):
        return f"TeacherSubstitution({self.lesson}, {self.class_name}, {self.teacher}, {self.subject}, {self.room}, " \
               f"{self.subs_from}, {self.hint}, {self.is_substitute_striked})"

    def to_dict(self):
        return {name: value for name, value in (("lesson", self.lesson), ("class", self.class_name),
                                                ("teacher", self.teacher), ("subject", self.subject),
                                                ("room", self.room), ("subs_from", self.subs_from), ("hint", self.hint),
                                                ("is_substitute_striked", self.is_substitute_striked)
                                                ) if value is not None}

    @lru_cache()
    def get_html_first_of_group(self, group_substitution_count, group, snippets, add_lesson_num):
        return snippets.get("substitution-row-first-teachers").format(
            group_substitution_count,
            group[0],
            self.lesson,
            self.class_name,
            self.teacher,
            self.subject,
            self.room,
            self.subs_from,
            self.hint,
            lesson_num=("lesson" + str(self.lesson_num)) if add_lesson_num else "",
            first_cell_classes=" striked" if group[1] else "",
            teacher_attrs=' class="striked"' if self.is_substitute_striked else ""
        )

    @lru_cache()
    def get_html(self, snippets, add_lesson_num):
        return snippets.get("substitution-row-teachers").format(
            self.lesson,
            self.class_name,
            self.teacher,
            self.subject,
            self.room,
            self.subs_from,
            self.hint,
            lesson_num=("lesson" + str(self.lesson_num)) if add_lesson_num else "",
            teacher_attrs=' class="striked"' if self.is_substitute_striked else ""
        )

    def get_hash(self, date, group_name):
        return hashlib.sha1((date + "-" + group_name[0] + "-" + self.lesson + "." + self.class_name + "." +
                             self.teacher + "." + self.subject + "." + self.room + "." + self.subs_from + "." +
                             self.hint + "." + str(self.is_substitute_striked)).encode()).hexdigest()

    def get_text(self):
        if self.subject.strip():
            fach = f"{self.subject} bei"
        else:
            fach = "Bei"
        if self.teacher.strip():
            lehrer = f" statt {self.teacher}"
        else:
            lehrer = ""
        if self.room.strip():
            raum = f" in Raum {self.room}"
        else:
            raum = ""
        return f"Vertretung {self.lesson}. Stunde: {fach} {self.class_name}{raum}{lehrer}."
