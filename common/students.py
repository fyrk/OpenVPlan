import hashlib
from functools import lru_cache

from common.base import BaseSubstitution, BaseSubstitutionGroup
from common.utils import sort_classes, REGEX_CLASS


class StudentSubstitutionGroup(BaseSubstitutionGroup):
    def __new__(cls, group_name, substitutions):
        self = super().__new__(cls, group_name, substitutions)
        self._sort_classes = sort_classes(self.group_name)
        return self

    def __lt__(self, other):
        return self._sort_classes < other._sort_classes

    def is_selected(self, parsed_selection):
        return is_class_selected(self.group_name, parsed_selection)


class StudentSubstitution(BaseSubstitution):
    def __init__(self, teacher, substitute, lesson, subject, room, subs_from, hint):
        super().__init__(lesson)
        self.teacher = teacher
        self.substitute = substitute
        self.subject = subject
        self.room = room
        self.subs_from = subs_from
        self.hint = hint

    def __repr__(self):
        return f"StudentSubstitution({self.lesson}, {self.teacher}, {self.substitute}, {self.subject}, {self.room}, " \
               f"{self.subs_from}, {self.hint})"

    def to_dict(self):
        return {name: value for name, value in (("lesson", self.lesson), ("lesson_num", self.lesson_num),
                                                ("teacher", self.teacher), ("substitute", self.substitute),
                                                ("subject", self.subject), ("room", self.room),
                                                ("subs_from", self.subs_from), ("hint", self.hint)
                                                ) if value is not None}

    @lru_cache()
    def get_html_first_of_group(self, group_substitution_count, group_name, snippets, add_lesson_num):
        return snippets.get(
            "substitution-row-first-students",
            substitution_count=group_substitution_count,
            group_name=group_name,
            teacher=self.teacher,
            substitute=self.substitute,
            lesson=self.lesson,
            subject=self.subject,
            room=self.room,
            subs_from=self.subs_from,
            hint=self.hint,
            lesson_num=("lesson" + str(self.lesson_num)) if add_lesson_num else ""
        )

    @lru_cache()
    def get_html(self, snippets, add_lesson_num):
        return snippets.get(
            "substitution-row-students",
            teacher=self.teacher,
            substitute=self.substitute,
            lesson=self.lesson,
            subject=self.subject,
            room=self.room,
            subs_from=self.subs_from,
            hint=self.hint,
            lesson_num=("lesson" + str(self.lesson_num)) if add_lesson_num else ""
        )

    def get_hash(self, date, class_name):
        return hashlib.sha1((date + "-" + class_name + "-" + self.teacher + "." + self.substitute + "." + self.lesson +
                             "." + self.subject + "." + self.room + "." + self.subs_from + "." + self.hint)
                            .encode()).hexdigest()

    def get_text(self):
        if self.teacher.strip():
            lehrer = f"bei {self.teacher} "
        else:
            lehrer = ""
        if ("---" in self.substitute or not self.substitute.strip()) \
                and "---" in self.subject and "---" in self.room:
            # lesson is canceled
            if "---" in self.substitute:
                message = f"Die {self.lesson}. Stunde {lehrer}fällt aus"
            else:
                message = f"Die {self.lesson}. Stunde {lehrer}findet nicht statt"
        else:
            if self.subject.strip():
                fach = f"{self.subject} "
            else:
                fach = ""
            if self.teacher == self.substitute:
                # room is changed
                if self.subject.strip():
                    fach = f"{self.subject} "
                else:
                    fach = ""
                message = f"Die {self.lesson}. Stunde {fach}{lehrer}findet in {self.room} statt"
            else:

                if self.room.strip():
                    raum = f" in {self.room}"
                else:
                    raum = ""
                if self.substitute.strip():
                    vertreter = f" durch {self.substitute}"
                else:
                    vertreter = ""
                message = f"Die {self.lesson}. Stunde {fach}{lehrer}wird{vertreter}{raum} vertreten"
        if self.subs_from.strip():
            if self.hint.strip():
                message += f" (Vertr. von {self.subs_from}, {self.hint})"
            else:
                message += f" (Vertr. von {self.subs_from})"
        else:
            if self.hint.strip():
                message += f" ({self.hint})"
        return message + "."


def parse_selection(text):
    if not text:
        return []
    selected_classes = []
    for selected_class in "".join(text.split()).split(","):
        if selected_class not in selected_classes:
            selected_classes.append(selected_class)
    return selected_classes


def split_class_name_lower(class_name):
    matches = REGEX_CLASS.search(class_name)
    if matches:
        return matches.group(1).lower(), matches.group(2).lower()
    return "", class_name.lower()


def is_class_selected(class_name, selection):
    if not class_name.strip():
        # class_name is empty, check if empty class name is in selection
        return ("", "") in selection
    class_name = class_name.lower()
    return any((selected_class[0] in class_name and selected_class[1] in class_name)
               for selected_class in selection if selected_class[0] or selected_class[1])
