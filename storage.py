"""SQLite persistence for sightings.

Column names match the original toot.py so an existing pork.db still opens.
"""

import datetime
import os
import sqlite3
import threading

DB_NAME = "pork.db"

# Two MACs within this distance of each other are treated as the same physical
# unit -- vehicles tend to hand out consecutive addresses across their radios.
GROUP_SPAN = 2


class Store:
    def __init__(self, directory="."):
        self.path = os.path.join(directory, DB_NAME)
        # The Kivy UI thread and the asyncio scan thread both reach this, so the
        # connection is shared and every statement goes through _lock.
        self._con = sqlite3.connect(self.path, check_same_thread=False)
        self._lock = threading.Lock()
        self._create_tables()

    def _create_tables(self):
        with self._lock, self._con:
            self._con.execute("""
                CREATE TABLE IF NOT EXISTS cop(
                    sqbssid TEXT PRIMARY KEY,
                    sqssid TEXT,
                    sqsignal TEXT,
                    protocal TEXT,
                    count INTEGER DEFAULT 0
                )""")
            self._con.execute("""
                CREATE TABLE IF NOT EXISTS groups(
                    group_id TEXT PRIMARY KEY,
                    bssids TEXT,
                    blemacs TEXT,
                    count INTEGER DEFAULT 1,
                    last_seen TEXT
                )""")

    def add_sighting(self, mac, label, signal, protocol):
        """Insert or bump a sighting.

        A missing label must not clobber a name recorded earlier, so the upsert
        keeps the stored value via COALESCE rather than branching into a second
        statement.
        """
        with self._lock, self._con:
            self._con.execute("""
                INSERT INTO cop (sqbssid, sqssid, sqsignal, protocal, count)
                VALUES (?, ?, ?, ?, 1)
                ON CONFLICT(sqbssid) DO UPDATE SET
                    count = count + 1,
                    sqsignal = excluded.sqsignal,
                    sqssid = COALESCE(excluded.sqssid, cop.sqssid),
                    protocal = excluded.protocal
            """, (mac, label, str(signal), protocol))

    def update_group(self, mac, is_ble=False):
        """Fold a MAC into a nearby group, or start a new one. Returns group id."""
        try:
            mac_int = int(mac.replace(":", ""), 16)
        except ValueError:
            return None

        column = "blemacs" if is_ble else "bssids"
        now = datetime.datetime.now().isoformat()

        with self._lock, self._con:
            rows = self._con.execute(
                "SELECT group_id, bssids, blemacs FROM groups").fetchall()

            for group_id, bssids, blemacs in rows:
                try:
                    group_int = int(group_id.replace(":", ""), 16)
                except ValueError:
                    continue
                if abs(mac_int - group_int) > GROUP_SPAN:
                    continue

                existing = blemacs if is_ble else bssids
                members = set(filter(None, (existing or "").split(",")))
                if mac in members:
                    self._con.execute(
                        "UPDATE groups SET last_seen = ? WHERE group_id = ?",
                        (now, group_id))
                else:
                    members.add(mac)
                    self._con.execute(
                        f"UPDATE groups SET {column} = ?, count = count + 1, "
                        "last_seen = ? WHERE group_id = ?",
                        (",".join(sorted(members)), now, group_id))
                return group_id

            self._con.execute(
                f"INSERT INTO groups (group_id, {column}, last_seen) "
                "VALUES (?, ?, ?)",
                (mac, mac, now))
            return mac

    def hits(self):
        with self._lock:
            return self._con.execute(
                "SELECT sqbssid, sqssid, sqsignal, protocal, count FROM cop "
                "ORDER BY count DESC").fetchall()

    def close(self):
        with self._lock:
            self._con.close()
