"""ETL tests: boundary processing, Oireachtas client, overrides, fail-soft refresh."""

import json
import sqlite3

import geopandas as gpd
import httpx
import pytest
import yaml
from shapely.geometry import box

from irl_reps.config import Settings
from irl_reps.etl.boundaries import process_constituency_frame
from irl_reps.etl.build import (
    STATUS_CARRIED_FORWARD,
    STATUS_FAILED_NO_PREVIOUS,
    STATUS_OK,
    refresh,
)
from irl_reps.etl.oireachtas import TDRecord, derive_email, fetch_tds

# --- boundary normalisation -----------------------------------------------------


def test_process_constituency_frame_strips_seat_count_and_dissolves():
    gdf = gpd.GeoDataFrame(
        {"ENG_NAME_VALUE": ["Mayo (5)", "Mayo (5)", "Dublin South-Central (4)"]},
        geometry=[box(0, 0, 1, 1), box(1, 0, 2, 1), box(5, 5, 6, 6)],
        crs=4326,
    )
    out = process_constituency_frame(gdf)
    assert sorted(out["name"]) == ["Dublin South-Central", "Mayo"]
    assert set(out.columns) == {"name", "geometry"}


# --- Oireachtas client ---------------------------------------------------------


def test_derive_email_from_structured_name_fields():
    # Simple forename + surname.
    assert derive_email("Mary", "O'Brien") == "mary.obrien@oireachtas.ie"
    # Multi-token (Irish) surname.
    assert derive_email("Seán", "Ó Murchú") == "sean.omurchu@oireachtas.ie"
    # Compound forename stays joined (the fullName-split bug this replaces).
    assert derive_email("Mary Lou", "McDonald") == "marylou.mcdonald@oireachtas.ie"
    # Hyphenated surname collapses to a single token.
    assert derive_email("Michael", "Healy-Rae") == "michael.healyrae@oireachtas.ie"
    # Missing either part yields no address.
    assert derive_email("Cher", None) is None
    assert derive_email(None, "Surname") is None


def _member(full_name: str, constituency: str, *, membership_end: str | None):
    """Build a minimal 34th-Dail member record for fetch_tds tests."""
    first, _, last = full_name.partition(" ")
    return {
        "member": {
            "fullName": full_name,
            "firstName": first,
            "lastName": last,
            "memberships": [
                {
                    "membership": {
                        "house": {"houseCode": "dail", "houseNo": "34"},
                        "dateRange": {"start": "2024-11-29", "end": membership_end},
                        "represents": [
                            {
                                "represent": {
                                    "representType": "constituency",
                                    "showAs": constituency,
                                    "dateRange": {"end": None},
                                }
                            }
                        ],
                        "parties": [
                            {"party": {"showAs": "Independent", "dateRange": {"end": None}}}
                        ],
                    }
                }
            ],
        }
    }


def test_fetch_tds_excludes_members_whose_seat_has_ended():
    """A TD who vacated their seat (membership end date set) is not returned.

    Regression for ceased members (e.g. elected to higher office) lingering in
    the datastore and pushing a constituency over its seat count.
    """
    page = {
        "results": [
            _member("Current TD", "Galway West", membership_end=None),
            _member("Departed TD", "Galway West", membership_end="2025-10-25"),
        ]
    }

    def handler(request: httpx.Request) -> httpx.Response:
        if int(request.url.params["skip"]) == 0:
            return httpx.Response(200, json=page)
        return httpx.Response(200, json={"results": []})

    records = fetch_tds(httpx.Client(transport=httpx.MockTransport(handler)))
    assert [r.name for r in records] == ["Current TD"]


def test_fetch_tds_parses_and_paginates():
    page = {
        "results": [
            {
                "member": {
                    "fullName": "Fionn Example",
                    "firstName": "Fionn",
                    "lastName": "Example",
                    "memberships": [
                        {
                            "membership": {
                                "house": {"houseCode": "dail", "houseNo": "34"},
                                "represents": [
                                    {
                                        "represent": {
                                            "representType": "constituency",
                                            "showAs": "Dublin South-Central",
                                        }
                                    }
                                ],
                                "parties": [
                                    {"party": {"showAs": "Labour", "dateRange": {"end": None}}}
                                ],
                            }
                        }
                    ],
                }
            }
        ]
    }
    calls = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        if int(request.url.params["skip"]) == 0:
            return httpx.Response(200, json=page)
        return httpx.Response(200, json={"results": []})

    client = httpx.Client(transport=httpx.MockTransport(handler))
    records = fetch_tds(client)
    assert len(records) == 1
    assert records[0] == TDRecord(
        name="Fionn Example",
        party="Labour",
        constituency="Dublin South-Central",
        email="fionn.example@oireachtas.ie",
    )
    assert len(calls) == 2  # one full page + one empty page


# --- refresh orchestration ------------------------------------------------------


def _td_fetcher(client: httpx.Client) -> list[TDRecord]:
    return [TDRecord(name="Fionn Example", party="Labour", constituency="Mayo", email=None)]


def _broken_td_fetcher(client: httpx.Client) -> list[TDRecord]:
    raise RuntimeError("Oireachtas API is down")


@pytest.fixture()
def etl_settings(tmp_path) -> Settings:
    return Settings(data_dir=tmp_path)


def _rows(db_path, table):
    conn = sqlite3.connect(db_path)
    try:
        return conn.execute(f"SELECT * FROM {table} ORDER BY name").fetchall()
    finally:
        conn.close()


def test_refresh_builds_datastore(etl_settings):
    report = refresh(etl_settings, td_fetcher=_td_fetcher, skip_boundaries=True)
    assert report.source_status == {"tds": STATUS_OK}
    assert len(_rows(etl_settings.db_path, "tds")) == 1
    assert report.last_updated  # ISO date stamped


def test_refresh_is_idempotent(etl_settings):
    for _ in range(2):
        refresh(etl_settings, td_fetcher=_td_fetcher, skip_boundaries=True)
    assert len(_rows(etl_settings.db_path, "tds")) == 1  # no duplication


def test_refresh_fail_soft_carries_forward_previous_data(etl_settings):
    """A broken Oireachtas fetch keeps the previous run's TDs."""
    refresh(etl_settings, td_fetcher=_td_fetcher, skip_boundaries=True)

    report = refresh(etl_settings, td_fetcher=_broken_td_fetcher, skip_boundaries=True)
    assert report.source_status["tds"] == STATUS_CARRIED_FORWARD
    names = [row[0] for row in _rows(etl_settings.db_path, "tds")]
    assert names == ["Fionn Example"]


def test_refresh_fail_soft_without_previous_data(etl_settings):
    report = refresh(etl_settings, td_fetcher=_broken_td_fetcher, skip_boundaries=True)
    assert report.source_status["tds"] == STATUS_FAILED_NO_PREVIOUS
    assert _rows(etl_settings.db_path, "tds") == []


def test_overrides_win_over_fetched_data(etl_settings):
    overrides = {
        "tds": {
            "update": [
                {
                    "match": {"name": "Fionn Example", "constituency": "Mayo"},
                    "set": {"email": "corrected@oireachtas.ie"},
                }
            ],
            "add": [
                {
                    "name": "Added Person",
                    "party": "Independent",
                    "email": None,
                    "constituency": "Mayo",
                }
            ],
        },
    }
    etl_settings.overrides_path.parent.mkdir(parents=True, exist_ok=True)
    etl_settings.overrides_path.write_text(yaml.safe_dump(overrides))

    report = refresh(etl_settings, td_fetcher=_td_fetcher, skip_boundaries=True)
    assert report.overrides_applied == 2

    rows = _rows(etl_settings.db_path, "tds")
    by_name = {row[0]: row for row in rows}
    assert by_name["Fionn Example"][2] == "corrected@oireachtas.ie"
    assert "Added Person" in by_name


def test_refresh_records_source_status_in_meta(etl_settings):
    refresh(etl_settings, td_fetcher=_td_fetcher, skip_boundaries=True)
    conn = sqlite3.connect(etl_settings.db_path)
    try:
        value = conn.execute(
            "SELECT value FROM meta WHERE key = 'source_status'"
        ).fetchone()[0]
    finally:
        conn.close()
    assert json.loads(value)["tds"] == STATUS_OK
