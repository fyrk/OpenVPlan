#  GaW-Vertretungsplan
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

import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple, Type, Union

import aiohttp

from ..parsers.base import BaseSubstitutionParser
from ..storage import SubstitutionStorage

_LOGGER = logging.getLogger("gawvertretung")


class BaseSubstitutionCrawler(ABC):
    _STORAGE_VERSION = b"\x01"

    _storage: "SubstitutionStorage"
    storage: "SubstitutionStorage"

    def __init__(self, last_version_id,
                 parser_class: Type[BaseSubstitutionParser], parser_options: Dict[str, Any]):
        self.last_version_id = last_version_id
        self._parser_class = parser_class
        self._parser_options = parser_options

        self._storage: Optional[SubstitutionStorage] = None

    @property
    def storage(self):
        return self._storage

    @abstractmethod
    async def update(self, session: aiohttp.ClientSession) \
            -> Tuple[bool, Optional[Dict[int, Dict[str, Union[str, List[str]]]]]]:
        ...
