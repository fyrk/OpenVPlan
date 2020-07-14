import json
import logging
import time
import sqlite3
import hashlib
import urllib
import urllib.parse
from typing import Generator, Tuple, List

_LOGGER = logging.getLogger("gawvertretung")

sqlite3.register_converter("JSON", json.loads)
sqlite3.register_adapter(dict, lambda d: json.dumps(d).encode("utf-8"))

sqlite3.register_converter("SELECTION", lambda s: [t.strip() for t in s.decode("utf-8").split(",")])
sqlite3.register_adapter(list, lambda selection: ",".join(selection).encode("utf-8"))


class SubstitutionPlanDBStorage:
    def __init__(self, filepath, **kwargs):
        self._connection = sqlite3.connect(filepath, detect_types=sqlite3.PARSE_DECLTYPES, **kwargs)
        self._connection.row_factory = sqlite3.Row
        self._cursor = self._connection.cursor()
        self._cursor.execute("CREATE TABLE IF NOT EXISTS push_subscriptions "
                             "(subscription JSON, endpoint TEXT PRIMARY KEY UNIQUE, endpoint_hash TEXT, "
                             "endpoint_origin TEXT, expiration_time TIMESTAMP,  selection SELECTION, "
                             "is_active BOOLEAN)")
        self._connection.commit()

    def close(self):
        self._connection.close()

    def add_push_subscription(self, subscription: dict, selection: str, is_active: bool):
        selection = selection.upper()
        try:
            endpoint = subscription["endpoint"]
            endpoint_hash = hashlib.blake2b(endpoint.encode("utf-8"), digest_size=3).hexdigest()
            parsed = urllib.parse.urlparse(endpoint)
            endpoint_origin = urllib.parse.urlunsplit((parsed.scheme, parsed.netloc, "", "", ""))
            expiration_time = subscription["expirationTime"]
        except Exception:
            raise ValueError("Wrong subscription object '" + str(subscription) + "'")
        self._cursor.execute("REPLACE INTO push_subscriptions VALUES (?,?,?,?,?,?,?)",
                             (subscription, endpoint, endpoint_hash, endpoint_origin, expiration_time, selection,
                              is_active))
        self._connection.commit()
        _LOGGER.debug(f"Add push subscription {endpoint_hash} ({endpoint_origin}) (is_active={is_active})")

    def iter_active_push_subscriptions(self, affected_groups: List[str]) -> Generator[Tuple[dict, List[str]], None,
                                                                                      None]:
        self._cursor.execute("SELECT * FROM push_subscriptions")
        current_time = time.time()
        for subscription_entry in self._cursor:
            expiration_time = subscription_entry["expiration_time"]
            if expiration_time is not None and expiration_time >= current_time:
                # TODO remove row
                continue
            if subscription_entry["is_active"]:
                selection = subscription_entry["selection"]
                if selection is None:
                    # selection is None when all groups are selected (empty selection)
                    yield subscription_entry, affected_groups
                elif intersection := [s for s in selection if s in affected_groups]:
                    yield subscription_entry, intersection
