"""Query history in a local SQLite file (no server needed)."""
import sqlite3
from contextlib import closing
from dataclasses import dataclass, field

SCHEMA = """
CREATE TABLE IF NOT EXISTS queries (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    expression  TEXT NOT NULL UNIQUE,
    source      TEXT NOT NULL DEFAULT 'local',
    created_at  TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);
CREATE TABLE IF NOT EXISTS results (
    id        INTEGER PRIMARY KEY AUTOINCREMENT,
    query_id  INTEGER NOT NULL REFERENCES queries(id) ON DELETE CASCADE,
    position  INTEGER NOT NULL,
    title     TEXT NOT NULL,
    content   TEXT NOT NULL
);
"""


@dataclass
class HistoryItem:
    id: int
    expression: str
    source: str
    created_at: str
    results: list = field(default_factory=list)  # [(title, content), ...]


class History:
    def __init__(self, path):
        self.path = str(path)
        with closing(self._connect()) as conn:
            conn.executescript(SCHEMA)

    def _connect(self):
        conn = sqlite3.connect(self.path)
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def save(self, expression, results, source="local"):
        """Store a query; re-running an expression moves it to the top instead of duplicating."""
        expression = expression.strip()
        with closing(self._connect()) as conn, conn:
            conn.execute("DELETE FROM queries WHERE expression = ?", (expression,))
            cur = conn.execute("INSERT INTO queries (expression, source) VALUES (?, ?)",
                               (expression, source))
            conn.executemany(
                "INSERT INTO results (query_id, position, title, content) VALUES (?, ?, ?, ?)",
                [(cur.lastrowid, i, t, c) for i, (t, c) in enumerate(results)])

    def fetch(self, limit=50):
        """Most recent ``limit`` queries, each with all of its results."""
        with closing(self._connect()) as conn:
            rows = conn.execute(
                "SELECT id, expression, source, created_at FROM queries ORDER BY id DESC LIMIT ?",
                (limit,)).fetchall()
            items = [HistoryItem(*r) for r in rows]
            by_id = {it.id: it for it in items}
            if by_id:
                marks = ",".join("?" * len(by_id))
                for qid, title, content in conn.execute(
                        f"SELECT query_id, title, content FROM results WHERE query_id IN ({marks}) "
                        "ORDER BY query_id, position", list(by_id)):
                    by_id[qid].results.append((title, content))
        return items

    def recent_expressions(self, limit=50):
        with closing(self._connect()) as conn:
            return [r[0] for r in conn.execute(
                "SELECT expression FROM queries ORDER BY id DESC LIMIT ?", (limit,))]

    def clear(self):
        with closing(self._connect()) as conn, conn:
            conn.execute("DELETE FROM results")
            conn.execute("DELETE FROM queries")
