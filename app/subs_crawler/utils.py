#  OpenVPlan
#  Copyright (C) 2019-2021  Florian Rädiker
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU Affero General Public License as published
#  by the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU Affero General Public License for more details.
#
#  You should have received a copy of the GNU Affero General Public License
#  along with this program.  If not, see <https://www.gnu.org/licenses/>.

import datetime
import re
import time
from functools import lru_cache
from typing import List, Tuple, Optional, Set


def create_date_timestamp(date: datetime.datetime):
    return int(time.mktime(date.date().timetuple()))


REGEX_GROUP_NAME = re.compile(r"^(\()?(\d+)(.*)(?(1)\)|)")

def split_class_name(class_name: str) -> Tuple[str, str]:
    matches = REGEX_GROUP_NAME.fullmatch(class_name)
    if matches:
        return matches.group(2), matches.group(3)
    return "", class_name


def strip_par(s: str):
    if s.startswith("(") and s.index(")") == len(s)-1:
        return s[1:-1].strip()
    return s


REGEX_CLASS = re.compile(r"^(\()?"
                         r"(\d+)([A-Za-z]*)"
                         r"(?(1)\)|)")

def parse_affected_groups(class_name: str) -> Tuple[Set[str], Optional[str]]:
    name = class_name.upper().strip()
    if not name:
        return set(), None
    affected_groups = set()
    count = 0
    while name:
        match = REGEX_CLASS.match(name)
        if match is None:
            if all(not c.isdigit() for c in name):
                # names without any digits can also be selected
                return {strip_par(name)}, strip_par(class_name)
            return {strip_par(name)}, None
        count += 1
        _, digits, letters = match.groups()
        affected_groups.add(digits)
        if len(letters) > 1:
            count += 1
        for letter in letters:
            affected_groups.add(digits + letter)
        name = name[match.span()[1]:]
    return affected_groups, strip_par(class_name) if count == 1 else None


def split_selection(selection: str) -> Optional[List[str]]:
    selected_groups = []
    for selected_group in "".join(selection.split()).split(","):
        if selected_group and selected_group not in selected_groups:
            selected_groups.append(selected_group)
    if not selected_groups:
        return None
    return selected_groups


REGEX_NUMBERS = re.compile(r"\d*")

@lru_cache(maxsize=128)
def get_lesson_num(lesson_string):
    try:
        return max(int(num.group(0)) for num in REGEX_NUMBERS.finditer(lesson_string) if num.group(0) != "")
    except ValueError:  # ValueError for max(...) got empty sequence
        return None
