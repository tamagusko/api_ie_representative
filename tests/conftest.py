"""Shared test fixtures: synthetic constituency boundaries and datastore.

Geometry layout (WGS84 squares, names mirror real constituencies):

- "Dublin South-Central" - covers (53.30..53.36, -6.32..-6.22).
- "Mayo" - covers (53.70..53.90, -9.70..-9.30).
- "Kerry" - covers (51.70..52.00, -10.00..-9.30); the west edge acts as "coastline".
- "Galway West" - covers (53.25..53.30, -9.10..-9.00); has NO TDs, to exercise
  the "no data" path.
"""

import sqlite3
from pathlib import Path

import geopandas as gpd
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from shapely.geometry import box

from irl_reps.api import create_app
from irl_reps.config import Settings
from irl_reps.repository import SCHEMA_SQL

DUBLIN_POINT = (53.3382, -6.2591)
RURAL_POINT = (53.80, -9.52)
COASTAL_EDGE_POINT = (51.85, -10.00)  # exactly on the west (coastal) boundary
NORTHERN_IRELAND_POINT = (54.60, -5.93)
OUTSIDE_BBOX_POINT = (48.8566, 2.3522)  # Paris

_CONSTITUENCIES = [
    # (constituency, min_lon, min_lat, max_lon, max_lat)
    ("Dublin South-Central", -6.32, 53.30, -6.22, 53.36),
    ("Mayo", -9.70, 53.70, -9.30, 53.90),
    ("Kerry", -10.00, 51.70, -9.30, 52.00),
    ("Galway West", -9.10, 53.25, -9.00, 53.30),  # no TDs
]

_TDS = [
    ("Fionn Example", "Labour", "fionn.example@oireachtas.ie", "Dublin South-Central"),
    ("Grainne Demo", "Sinn Fein", None, "Dublin South-Central"),
    ("Hugh Placeholder", "Fianna Fail", None, "Mayo"),
    ("Ide Specimen", "Independent", None, "Kerry"),
]

LAST_UPDATED = "2026-06-01"


def build_boundaries_parquet(path: Path) -> None:
    rows = [
        {"name": name, "geometry": box(min_lon, min_lat, max_lon, max_lat)}
        for name, min_lon, min_lat, max_lon, max_lat in _CONSTITUENCIES
    ]
    gdf = gpd.GeoDataFrame(pd.DataFrame(rows), geometry="geometry", crs=4326)
    path.parent.mkdir(parents=True, exist_ok=True)
    gdf.to_parquet(path)


def build_representatives_db(path: Path) -> None:
    conn = sqlite3.connect(path)
    try:
        conn.executescript(SCHEMA_SQL)
        conn.executemany(
            "INSERT INTO tds (name, party, email, constituency) VALUES (?, ?, ?, ?)", _TDS
        )
        conn.execute("INSERT INTO meta (key, value) VALUES ('last_updated', ?)", (LAST_UPDATED,))
        conn.commit()
    finally:
        conn.close()


@pytest.fixture(scope="session")
def settings(tmp_path_factory) -> Settings:
    data_dir = tmp_path_factory.mktemp("data")
    test_settings = Settings(data_dir=data_dir)
    build_boundaries_parquet(test_settings.boundaries_path)
    build_representatives_db(test_settings.db_path)
    return test_settings


@pytest.fixture(scope="session")
def client(settings) -> TestClient:
    with TestClient(create_app(settings), raise_server_exceptions=False) as test_client:
        yield test_client
