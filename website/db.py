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

import datetime
import hashlib
import json
import logging
import sqlite3
import urllib.parse
from typing import Iterable

_LOGGER = logging.getLogger("gawvertretung")

sqlite3.register_converter("JSON", json.loads)
sqlite3.register_adapter(dict, lambda d: json.dumps(d).encode("utf-8"))

sqlite3.register_converter("SELECTION", lambda s: [t.strip() for t in s.decode("utf-8").split(",")])
sqlite3.register_adapter(list, lambda selection: ",".join(selection).encode("utf-8"))


def hash_endpoint(endpoint):
    return hashlib.blake2b(endpoint.encode("utf-8"), digest_size=3).hexdigest()


class SubstitutionPlanDB:
    def __init__(self, filepath, **kwargs):
        self._connection = sqlite3.connect(filepath, detect_types=sqlite3.PARSE_DECLTYPES|sqlite3.PARSE_COLNAMES,
                                           **kwargs)
        self._connection.row_factory = sqlite3.Row
        self._cursor = self._connection.cursor()

        self._cursor.execute("PRAGMA main.user_version;")
        user_version = self._cursor.fetchone()["user_version"]
        if user_version == 0:
            self._cursor.execute("""
            CREATE TABLE IF NOT EXISTS push_subscriptions2
            (plan_id TEXT, subscription JSON, selection SELECTION, is_active BOOLEAN, endpoint_hash TEXT,
             endpoint_origin TEXT, last_change TIMESTAMP, unique(plan_id, subscription))""")
        """if user_version <= 1:
            self._cursor.execute("ALTER TABLE push_subscriptions2 ADD COLUMN dnt_enabled BOOLEAN")
        if user_version <= 2:
            self._cursor.execute("ALTER TABLE push_subscriptions2 ADD COLUMN user_agent TEXT")
            self._cursor.execute("PRAGMA main.user_version = 3;")"""
        if user_version <= 3:
            # remove columns dnt_enabled and user_agent
            self._cursor.executescript("""
            CREATE TEMPORARY TABLE push_subscriptions_tmp(plan_id TEXT, subscription JSON, selection SELECTION,
                                                          is_active BOOLEAN, endpoint_hash TEXT, endpoint_origin TEXT,
                                                          last_change TIMESTAMP, unique(plan_id, subscription));
            INSERT INTO push_subscriptions_tmp SELECT plan_id, subscription, selection, is_active, endpoint_hash, 
                                                      endpoint_origin, last_change FROM push_subscriptions2;
            DROP TABLE push_subscriptions2;
            CREATE TABLE push_subscriptions2(plan_id TEXT, subscription JSON, selection SELECTION, is_active BOOLEAN,
                                             endpoint_hash TEXT, endpoint_origin TEXT, last_change TIMESTAMP,
                                             unique(plan_id, subscription));
            INSERT INTO push_subscriptions2 SELECT plan_id, subscription, selection, is_active, endpoint_hash, 
                                                   endpoint_origin, last_change FROM push_subscriptions_tmp;
            DROP TABLE push_subscriptions_tmp;""")
            self._cursor.execute("PRAGMA main.user_version = 4;")
        if user_version <= 4:
            self._cursor.execute(
                "CREATE TABLE IF NOT EXISTS last_substitution_version_id (plan_id TEXT unique, version_id JSON)")
            self._cursor.execute("PRAGMA main.user_version = 5;")
        if user_version <= 5:
            # push_subscriptions2: remove is_active, remove endpoint_origin, remove endpoint_hash, add endpoint,
            #                      new primary key: (plan_id, endpoint)
            self._cursor.execute("""
            CREATE TEMPORARY TABLE push_subscriptions_tmp(plan_id TEXT, endpoint TEXT, subscription JSON,
                                                          selection SELECTION,
                                                          last_change TIMESTAMP, unique(plan_id, endpoint))""")
            for row in self._cursor.execute("SELECT * FROM push_subscriptions2 WHERE is_active=1").fetchall():
                subscription = row["subscription"]
                endpoint = subscription["endpoint"]
                self._cursor.execute(
                    "REPLACE INTO push_subscriptions_tmp VALUES (?,?,?,?,?)",
                    (row["plan_id"], endpoint, row["subscription"], row["selection"], row["last_change"]))
            self._cursor.executescript("""
            DROP TABLE push_subscriptions2;
            CREATE TABLE push_subscriptions2(plan_id TEXT, endpoint TEXT, subscription JSON,
                                             selection SELECTION, last_change TIMESTAMP, unique(plan_id, endpoint));
            INSERT INTO push_subscriptions2 SELECT plan_id, endpoint, subscription,
                                                   selection, last_change FROM push_subscriptions_tmp;
            DROP TABLE push_subscriptions_tmp;
            """)
            self._cursor.execute("PRAGMA main.user_version = 6;")

        self._connection.commit()

    def commit(self):
        self._connection.commit()

    def close(self):
        self._connection.close()

    def set_substitutions_version_id(self, plan_id: str, version_id: str):
        self._cursor.execute("REPLACE INTO last_substitution_version_id VALUES (?,?)", (plan_id, version_id))
        self._connection.commit()

    def get_substitutions_version_id(self, plan_id: str) -> str:
        self._cursor.execute("SELECT version_id FROM last_substitution_version_id WHERE plan_id=?", (plan_id,))
        row = self._cursor.fetchone()
        return row["version_id"] if row is not None else None

    def add_push_subscription(self, plan_id: str, subscription: dict, selection: str):
        selection = selection.upper()
        try:
            endpoint = subscription["endpoint"]
        except Exception:
            raise ValueError("Wrong subscription object '" + str(subscription) + "'")
        self._cursor.execute("REPLACE INTO push_subscriptions2 VALUES (?,?,?,?,?)",
                             (plan_id, endpoint, subscription, selection, datetime.datetime.now()))
        _LOGGER.debug(f"Add push subscription {plan_id}-{hash_endpoint(endpoint)[:6]} "
                      f"(origin: {urllib.parse.urlparse(endpoint).netloc})")

    def iter_push_subscriptions(self, plan_id: str) -> Iterable[sqlite3.Row]:
        return self._cursor.execute("SELECT * FROM push_subscriptions2 WHERE plan_id=?", (plan_id,))

    def delete_push_subscription(self, plan_id: str, endpoint: str):
        self._cursor.execute("DELETE FROM push_subscriptions2 WHERE plan_id=? AND endpoint=?",
                             (plan_id, endpoint))
        _LOGGER.debug(f"Delete push subscription {plan_id}-{hash_endpoint(endpoint)[:6]}")
