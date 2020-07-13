import json
import sqlite3
from typing import Set, Generator, Optional

sqlite3.register_converter("JSON", json.loads)
sqlite3.register_adapter(dict, lambda d: json.dumps(d).encode("utf-8"))

sqlite3.register_converter("SELECTION", lambda s: set(t.strip() for t in s.decode("utf-8").split(",")))
sqlite3.register_adapter(list, lambda selection: ",".join(selection).encode("utf-8"))


class SubstitutionPlanDBStorage:
    def __init__(self, filepath, **kwargs):
        self._connection = sqlite3.connect(filepath, detect_types=sqlite3.PARSE_DECLTYPES, **kwargs)
        self._cursor = self._connection.cursor()
        self._cursor.execute("CREATE TABLE IF NOT EXISTS push_subscriptions "
                             "(subscription JSON PRIMARY KEY UNIQUE, selection SELECTION, is_active BOOLEAN)")
        self._connection.commit()

    def close(self):
        self._connection.close()

    def add_push_subscription(self, subscription: dict, selection: str, is_active: bool):
        assert type(subscription) == dict and type(selection) == str and type(is_active) == bool
        self._cursor.execute("REPLACE INTO push_subscriptions VALUES (?,?,?)", (subscription, selection, is_active))
        self._connection.commit()

    def iter_active_push_subscriptions(self, affected_groups: Set[str]) -> Generator[dict, Set[str]]:
        self._cursor.execute("SELECT * FROM push_subscriptions")
        for subscription, selection, is_active in self._cursor:
            if is_active:
                if selection is None:
                    # selection is None when all groups are selected (empty selection)
                    yield subscription, affected_groups
                elif intersection := affected_groups.intersection(selection):
                    yield subscription, intersection
