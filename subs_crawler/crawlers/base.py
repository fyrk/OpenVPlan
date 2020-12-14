import logging
import pickle
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

    def __init__(self, parser_class: Type[BaseSubstitutionParser], parser_options: Dict[str, Any]):
        self._parser_class = parser_class
        self._parser_options = parser_options

        self._storage: Optional[SubstitutionStorage] = None

    @property
    def storage(self):
        return self._storage

    def serialize(self, filepath: str):
        # noinspection PyBroadException
        try:
            with open(filepath, "wb") as f:
                f.write(self._STORAGE_VERSION)
                pickle.dump(self._storage, f)
            _LOGGER.debug(f"Wrote substitutions to '{filepath}'")
        except Exception:
            _LOGGER.exception(f"Could not serialize substitutions to '{filepath}'")

    def deserialize(self, filepath: str):
        # noinspection PyBroadException
        try:
            with open(filepath, "rb") as f:
                if f.read(1) != self._STORAGE_VERSION:
                    _LOGGER.warning(f"Could not deserialize substitutions from '{filepath}': "
                                    "Storage versions do not match")
                    return None
                self._storage = pickle.load(f)
        except Exception:
            _LOGGER.warning(f"Could not deserialize substitutions from '{filepath}'")
        else:
            if self._storage is not None:
                _LOGGER.debug(f"Loaded substitutions from '{filepath}' with status '{self._storage.status}'")

    @abstractmethod
    async def update(self, session: aiohttp.ClientSession) \
            -> Tuple[bool, Optional[Dict[int, Dict[str, Union[str, List[str]]]]]]:
        ...
