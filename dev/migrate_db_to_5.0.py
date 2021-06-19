"""
This script reads the {students|teachers}.sqlite3 databases and writes them into the new one (db.sqlite3).
"""
import os.path
import sqlite3
import sys

sys.path.append(os.path.abspath("."))
print(sys.path)

from website.db import SubstitutionPlanDB


db = SubstitutionPlanDB("dev/production_db.sqlite3")

for plan_id in ("students", "teachers"):
    con = sqlite3.connect(f"_dev/production_update_210619/production_{plan_id}.sqlite3",
                          detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES)
    con.row_factory = sqlite3.Row
    cur = con.cursor()
    for subscription in cur.execute("SELECT * FROM push_subscriptions"):
        selection = subscription["selection"]
        # noinspection PyTypeChecker
        db.add_push_subscription(plan_id, subscription["subscription"], ",".join(selection) if selection else "",
                                 subscription["is_active"], False, None)
