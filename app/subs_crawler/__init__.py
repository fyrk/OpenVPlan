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

from .crawlers.dsbmobile import DsbmobileSubstitutionCrawler
from .crawlers.multipage import MultiPageSubstitutionCrawler
from .crawlers.webuntis import WebuntisCrawler
from .parsers.untis import UntisSubstitutionParser

__all__ = ["CRAWLERS", "PARSERS"]

CRAWLERS = {
    "multipage": MultiPageSubstitutionCrawler,
    "dsbmobile": DsbmobileSubstitutionCrawler,
    "webuntis": WebuntisCrawler
}

PARSERS = {
    "untis": UntisSubstitutionParser
}


def get_crawler(name: str):
    try:
        return CRAWLERS[name]
    except KeyError:
        raise ValueError(f"Invalid crawler name '{name}")
