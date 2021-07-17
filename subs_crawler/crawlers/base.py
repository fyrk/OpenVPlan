import logging
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple, Type, Union

import aiohttp

from subs_crawler.parsers.base import BaseSubstitutionParser
from subs_crawler.storage import SubstitutionStorage

_LOGGER = logging.getLogger("gawvertretung")


class BaseSubstitutionCrawler(ABC):
    _STORAGE_VERSION = b"\x01"

    _storage: "SubstitutionStorage"
    storage: "SubstitutionStorage"

    def __init__(self, last_version_id: Optional[str],
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
