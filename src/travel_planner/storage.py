"""SQLite fiyat geçmişi ve gönderilmiş bildirimler."""

from __future__ import annotations

import sqlite3
import statistics
from datetime import datetime, timedelta, timezone
from pathlib import Path

SCHEMA = """
CREATE TABLE IF NOT EXISTS observations (
    id INTEGER PRIMARY KEY,
    scanned_at TEXT NOT NULL,
    origin TEXT NOT NULL,
    destination TEXT NOT NULL,
    depart TEXT NOT NULL,
    ret TEXT NOT NULL,
    price REAL NOT NULL,
    currency TEXT NOT NULL,
    airline TEXT,
    transfers INTEGER,
    link TEXT
);
CREATE INDEX IF NOT EXISTS idx_obs_route
    ON observations (origin, destination, currency, scanned_at);

CREATE TABLE IF NOT EXISTS notifications (
    origin TEXT NOT NULL,
    destination TEXT NOT NULL,
    depart TEXT NOT NULL,
    ret TEXT NOT NULL,
    price REAL NOT NULL,
    notified_at TEXT NOT NULL,
    PRIMARY KEY (origin, destination, depart, ret)
);
"""


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Storage:
    def __init__(self, path: str):
        if path != ":memory:":
            Path(path).parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(path)
        self.conn.executescript(SCHEMA)

    def add_observations(self, rows: list[tuple], scanned_at: datetime | None = None) -> None:
        """rows: (origin, destination, depart, ret, price, currency, airline, transfers, link)"""
        ts = (scanned_at or utcnow()).isoformat()
        self.conn.executemany(
            "INSERT INTO observations (scanned_at, origin, destination, depart, ret, price,"
            " currency, airline, transfers, link) VALUES (?,?,?,?,?,?,?,?,?,?)",
            [(ts, *row) for row in rows],
        )
        self.conn.commit()

    def baseline(
        self, origin: str, destination: str, currency: str, days: int, min_samples: int
    ) -> float | None:
        """Rotanın 'normal' hafta sonu fiyatı: son `days` gündeki gözlemlerin medyanı."""
        since = (utcnow() - timedelta(days=days)).isoformat()
        prices = [
            p
            for (p,) in self.conn.execute(
                "SELECT price FROM observations WHERE origin=? AND destination=? AND currency=?"
                " AND scanned_at >= ?",
                (origin, destination, currency, since),
            )
        ]
        if len(prices) < min_samples:
            return None
        return statistics.median(prices)

    def last_notified_price(self, origin: str, destination: str, depart: str, ret: str):
        row = self.conn.execute(
            "SELECT price FROM notifications WHERE origin=? AND destination=? AND depart=? AND ret=?",
            (origin, destination, depart, ret),
        ).fetchone()
        return row[0] if row else None

    def mark_notified(self, origin: str, destination: str, depart: str, ret: str, price: float):
        self.conn.execute(
            "INSERT OR REPLACE INTO notifications VALUES (?,?,?,?,?,?)",
            (origin, destination, depart, ret, price, utcnow().isoformat()),
        )
        self.conn.commit()

    def prune(self, keep_days: int) -> None:
        cutoff = (utcnow() - timedelta(days=keep_days)).isoformat()
        today = utcnow().date().isoformat()
        self.conn.execute("DELETE FROM observations WHERE scanned_at < ?", (cutoff,))
        self.conn.execute("DELETE FROM notifications WHERE depart < ?", (today,))
        self.conn.commit()
