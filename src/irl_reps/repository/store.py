"""SQLite-backed read access to the representative datastore.

The database file is an artifact produced by the ETL (`refresh-reps`). The API
only ever reads it. Plain SQLite suffices: all spatial work happens in the
in-memory STRtree, so no spatial extension is needed at query time.
"""

import sqlite3
from dataclasses import dataclass
from pathlib import Path

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS tds (
    name TEXT NOT NULL,
    party TEXT,
    email TEXT,
    constituency TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_tds_constituency ON tds (constituency);

CREATE TABLE IF NOT EXISTS meta (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
"""


@dataclass(frozen=True)
class RepresentativeRow:
    name: str
    party: str | None
    email: str | None


class RepresentativeStore:
    """Read-only queries against the representative SQLite database."""

    def __init__(self, db_path: Path) -> None:
        if not db_path.exists():
            raise FileNotFoundError(
                f"Representative database not found: {db_path}. Run `refresh-reps` to build it."
            )
        self._conn = sqlite3.connect(f"file:{db_path}?mode=ro", uri=True, check_same_thread=False)
        self._conn.row_factory = sqlite3.Row

    def tds_for(self, constituency: str) -> list[RepresentativeRow]:
        rows = self._conn.execute(
            "SELECT name, party, email FROM tds WHERE constituency = ? ORDER BY name",
            (constituency,),
        ).fetchall()
        return [_to_row(r) for r in rows]

    def last_updated(self) -> str | None:
        row = self._conn.execute(
            "SELECT value FROM meta WHERE key = 'last_updated'"
        ).fetchone()
        return row["value"] if row else None

    def close(self) -> None:
        self._conn.close()


def _to_row(row: sqlite3.Row) -> RepresentativeRow:
    return RepresentativeRow(name=row["name"], party=row["party"], email=row["email"])
