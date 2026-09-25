"""Persistência de probes e sessões (SQLite + export JSON)."""
from __future__ import annotations

import json
import os
import sqlite3
import time
from typing import Any, Dict, List

DEFAULT_DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "optilag_data.db")


class Persistence:
    def __init__(self, db_path: str = DEFAULT_DB):
        self.db_path = db_path
        self._init_db()

    def _connect(self) -> sqlite3.Connection:
        conn = sqlite3.connect(self.db_path, check_same_thread=False, timeout=10)
        conn.row_factory = sqlite3.Row
        # Garante que writes são flushed (ajuda no Windows a libertar o lock)
        conn.isolation_level = None  # autocommit
        return conn

    def _init_db(self):
        conn = self._connect()
        try:
            conn.executescript(
                """
                CREATE TABLE IF NOT EXISTS probes (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    ts REAL NOT NULL,
                    udp INTEGER,
                    tcp INTEGER,
                    icmp INTEGER,
                    combined INTEGER,
                    method TEXT
                );
                CREATE TABLE IF NOT EXISTS sessions (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    started REAL NOT NULL,
                    ended REAL,
                    route TEXT,
                    game TEXT,
                    user TEXT,
                    ping_before INTEGER,
                    ping_after INTEGER,
                    duration_sec INTEGER
                );
                CREATE INDEX IF NOT EXISTS idx_probes_ts ON probes(ts);
                """
            )
        finally:
            conn.close()

    def save_probe(self, probe) -> None:
        conn = self._connect()
        try:
            conn.execute(
                "INSERT INTO probes (ts, udp, tcp, icmp, combined, method) VALUES (?,?,?,?,?,?)",
                (
                    getattr(probe, "timestamp", time.time()),
                    getattr(probe, "udp", None),
                    getattr(probe, "tcp", None),
                    getattr(probe, "icmp", None),
                    getattr(probe, "combined", None),
                    getattr(probe, "method", None),
                ),
            )
        finally:
            conn.close()

    def recent_probes(self, limit: int = 50) -> List[Dict[str, Any]]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM probes ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def save_session(
        self,
        started: float,
        ended: float,
        route: str,
        game: str = "",
        user: str = "",
        ping_before: int = 0,
        ping_after: int = 0,
    ) -> None:
        conn = self._connect()
        try:
            conn.execute(
                """INSERT INTO sessions
                   (started, ended, route, game, user, ping_before, ping_after, duration_sec)
                   VALUES (?,?,?,?,?,?,?,?)""",
                (
                    started,
                    ended,
                    route,
                    game,
                    user,
                    ping_before,
                    ping_after,
                    int(ended - started),
                ),
            )
        finally:
            conn.close()

    def recent_sessions(self, limit: int = 30) -> List[Dict[str, Any]]:
        conn = self._connect()
        try:
            rows = conn.execute(
                "SELECT * FROM sessions ORDER BY id DESC LIMIT ?", (limit,)
            ).fetchall()
            return [dict(r) for r in rows]
        finally:
            conn.close()

    def export_json(self, path: str) -> str:
        data = {
            "probes": self.recent_probes(200),
            "sessions": self.recent_sessions(100),
            "exported_at": time.time(),
        }
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        return path

    def stats(self) -> Dict[str, Any]:
        conn = self._connect()
        try:
            n_probes = conn.execute("SELECT COUNT(*) c FROM probes").fetchone()["c"]
            n_sess = conn.execute("SELECT COUNT(*) c FROM sessions").fetchone()["c"]
            avg = conn.execute(
                "SELECT AVG(combined) a FROM probes WHERE combined IS NOT NULL"
            ).fetchone()["a"]
            return {
                "probes": n_probes,
                "sessions": n_sess,
                "avg_ping": round(avg, 1) if avg else None,
            }
        finally:
            conn.close()
