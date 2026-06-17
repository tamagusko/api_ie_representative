"""Refresh orchestrator: rebuild the representative datastore.

Idempotent, atomic, fail-soft per source:
- builds into a temporary database, then ``os.replace`` over the live file;
- a failed source (Oireachtas API error) carries forward that source's rows
  from the previous database instead of aborting;
- the manual overrides file is applied last, so it always wins.
"""

import json
import logging
import os
import sqlite3
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import date
from pathlib import Path

import httpx

from irl_reps.config import Settings
from irl_reps.etl import boundaries, oireachtas
from irl_reps.etl.overrides import apply_overrides, load_overrides
from irl_reps.repository import SCHEMA_SQL

logger = logging.getLogger(__name__)

STATUS_OK = "ok"
STATUS_CARRIED_FORWARD = "carried_forward"
STATUS_FAILED_NO_PREVIOUS = "failed_no_previous_data"

TdFetcher = Callable[[httpx.Client], list[oireachtas.TDRecord]]


@dataclass(frozen=True)
class RefreshReport:
    last_updated: str
    source_status: dict[str, str] = field(default_factory=dict)
    overrides_applied: int = 0


def _carry_forward(
    conn: sqlite3.Connection, previous_db: Path, table: str, where: str, params: tuple
) -> int:
    """Copy rows for one failed source from the previous database.

    Uses a separate read-only connection (ATTACH inside the build transaction
    would deadlock against the new database's write lock).
    """
    if not previous_db.exists():
        return 0
    previous = sqlite3.connect(f"file:{previous_db}?mode=ro", uri=True)
    try:
        rows = previous.execute(f"SELECT * FROM {table} WHERE {where}", params).fetchall()
    except sqlite3.Error as exc:
        logger.warning(
            "carry-forward read failed",
            extra={"ctx": {"table": table, "error": str(exc)}},
        )
        return 0
    finally:
        previous.close()
    if rows:
        placeholders = ", ".join("?" for _ in rows[0])
        conn.executemany(f"INSERT INTO {table} VALUES ({placeholders})", rows)
    return len(rows)


def _load_tds(
    conn: sqlite3.Connection,
    client: httpx.Client,
    td_fetcher: TdFetcher,
    previous_db: Path,
    status: dict[str, str],
) -> None:
    try:
        tds = td_fetcher(client)
    except Exception as exc:  # noqa: BLE001 - fail-soft boundary by design
        logger.warning("TD fetch failed", extra={"ctx": {"error": str(exc)}})
        copied = _carry_forward(conn, previous_db, "tds", "1=1", ())
        status["tds"] = STATUS_CARRIED_FORWARD if copied else STATUS_FAILED_NO_PREVIOUS
        return
    conn.executemany(
        "INSERT INTO tds (name, party, email, constituency) VALUES (?, ?, ?, ?)",
        [(t.name, t.party, t.email, t.constituency) for t in tds],
    )
    status["tds"] = STATUS_OK


def refresh(
    settings: Settings,
    *,
    client: httpx.Client | None = None,
    td_fetcher: TdFetcher | None = None,
    skip_boundaries: bool = False,
    force_boundaries: bool = False,
) -> RefreshReport:
    """Rebuild the representative datastore. Safe to re-run at any time."""
    own_client = client is None
    http_client = client or httpx.Client(headers={"User-Agent": "irl-reps-etl/0.2"})
    active_td_fetcher = td_fetcher if td_fetcher is not None else oireachtas.fetch_tds

    try:
        if not skip_boundaries:
            boundaries.ensure_boundaries(settings, http_client, force=force_boundaries)

        settings.data_dir.mkdir(parents=True, exist_ok=True)
        tmp_path = settings.db_path.with_suffix(".db.tmp")
        tmp_path.unlink(missing_ok=True)

        status: dict[str, str] = {}
        conn = sqlite3.connect(tmp_path)
        try:
            conn.executescript(SCHEMA_SQL)
            _load_tds(conn, http_client, active_td_fetcher, settings.db_path, status)
            overrides_applied = apply_overrides(conn, load_overrides(settings.overrides_path))

            last_updated = date.today().isoformat()
            conn.executemany(
                "INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)",
                [
                    ("last_updated", last_updated),
                    ("source_status", json.dumps(status, sort_keys=True)),
                ],
            )
            conn.commit()
        finally:
            conn.close()

        os.replace(tmp_path, settings.db_path)
        report = RefreshReport(
            last_updated=last_updated,
            source_status=status,
            overrides_applied=overrides_applied,
        )
        logger.info(
            "refresh complete",
            extra={"ctx": {"db": str(settings.db_path), **status}},
        )
        return report
    finally:
        if own_client:
            http_client.close()
