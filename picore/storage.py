"""Query history in a local SQLite file (no server needed).

Failure policy: history is a convenience, so it must never stop the app. A damaged
database file is moved aside (history.db.corrupt-<time>) and a fresh one is started;
if no file can be used at all, history lives in memory for this session. ``note``
says what happened so the UI can tell the user.
"""
import logging
import sqlite3
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)

MAX_CONTENT = 20_000        # characters stored per result card
MAX_EXPRESSION = 2_000

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


def _text(value, limit):
    text = "" if value is None else str(value)
    return text if len(text) <= limit else text[:limit] + " …(truncated)"


class History:
    def __init__(self, path):
        self.path = str(path)
        self.persistent = True
        self.note = ""
        self._memory = None
        try:
            self._init()
        except sqlite3.Error as exc:
            log.warning("history database unusable (%s): %s", self.path, exc)
            moved = self._quarantine()
            try:
                if moved is None:
                    raise
                self._init()
                self.note = f"The history file was damaged, so a fresh one was started (old file kept as {moved.name})."
            except sqlite3.Error:
                self._memory = sqlite3.connect(":memory:", check_same_thread=False)
                self._memory.executescript(SCHEMA)
                self.persistent = False
                self.note = "History can't be saved this session: the history file couldn't be opened."

    def _init(self):
        with self._db() as conn:
            conn.executescript(SCHEMA)
            conn.execute("SELECT count(*) FROM queries").fetchone()      # proves the file is readable

    def _quarantine(self):
        p = Path(self.path)
        if not p.is_file():
            return None
        target = p.with_name(f"{p.name}.corrupt-{int(time.time())}")
        try:
            p.replace(target)
        except OSError:
            return None
        return target

    @contextmanager
    def _db(self, write=False):
        conn = self._memory
        if conn is None:
            conn = sqlite3.connect(self.path)
            conn.execute("PRAGMA foreign_keys = ON")
        try:
            if write:
                with conn:                       # commit, or roll back on error
                    yield conn
            else:
                yield conn
        finally:
            if conn is not self._memory:
                conn.close()

    def save(self, expression, results, source="local"):
        """Store a query; re-running an expression moves it to the top instead of duplicating."""
        expression = _text(expression, MAX_EXPRESSION).strip()
        rows = [(_text(t, 200), _text(c, MAX_CONTENT)) for t, c in results]
        with self._db(write=True) as conn:
            conn.execute("DELETE FROM queries WHERE expression = ?", (expression,))
            cur = conn.execute("INSERT INTO queries (expression, source) VALUES (?, ?)", (expression, str(source)))
            conn.executemany(
                "INSERT INTO results (query_id, position, title, content) VALUES (?, ?, ?, ?)",
                [(cur.lastrowid, i, t, c) for i, (t, c) in enumerate(rows)])

    def fetch(self, limit=50):
        """Most recent ``limit`` queries, each with all of its results."""
        with self._db() as conn:
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
        with self._db() as conn:
            return [r[0] for r in conn.execute(
                "SELECT expression FROM queries ORDER BY id DESC LIMIT ?", (limit,))]

    def clear(self):
        with self._db(write=True) as conn:
            conn.execute("DELETE FROM results")
            conn.execute("DELETE FROM queries")
