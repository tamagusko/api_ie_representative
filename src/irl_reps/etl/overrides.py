"""Manual override file: hand-maintained corrections applied after fetching.

``data/overrides.yaml`` structure (all sections optional):

    tds:
      add:
        - {name: "...", party: "...", email: "...", constituency: "..."}
      update:
        - match: {name: "...", constituency: "..."}
          set: {email: "..."}
      remove:
        - {name: "..."}

Overrides always win over fetched data because they run last.
"""

import logging
import sqlite3
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

_TABLES = {
    "tds": ("name", "party", "email", "constituency"),
}


def load_overrides(path: Path) -> dict:
    if not path.exists():
        return {}
    with path.open() as fh:
        data = yaml.safe_load(fh) or {}
    if not isinstance(data, dict):
        raise ValueError(f"Overrides file {path} must contain a mapping at the top level")
    return data


def _where(match: dict[str, str]) -> tuple[str, list[str]]:
    clause = " AND ".join(f"{key} = ?" for key in match)
    return clause, list(match.values())


def apply_overrides(conn: sqlite3.Connection, overrides: dict) -> int:
    """Apply add/update/remove operations. Returns number of operations applied."""
    applied = 0
    for table, columns in _TABLES.items():
        section = overrides.get(table) or {}
        for row in section.get("add") or []:
            values = [row.get(col) for col in columns]
            placeholders = ", ".join("?" for _ in columns)
            conn.execute(
                f"INSERT INTO {table} ({', '.join(columns)}) VALUES ({placeholders})", values
            )
            applied += 1
        for op in section.get("update") or []:
            clause, params = _where(op["match"])
            updates = op["set"]
            set_clause = ", ".join(f"{key} = ?" for key in updates)
            conn.execute(
                f"UPDATE {table} SET {set_clause} WHERE {clause}",
                [*updates.values(), *params],
            )
            applied += 1
        for match in section.get("remove") or []:
            clause, params = _where(match)
            conn.execute(f"DELETE FROM {table} WHERE {clause}", params)
            applied += 1
    logger.info("overrides applied", extra={"ctx": {"operations": applied}})
    return applied
