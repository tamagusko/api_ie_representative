"""Schema validation."""

import pytest
from pydantic import ValidationError

from irl_reps.schemas import (
    Area,
    ConstituencyTDs,
    Coordinate,
    LookupResponse,
    Representative,
)


def test_coordinate_accepts_irish_point():
    coordinate = Coordinate(lat=53.3382, lon=-6.2591)
    assert coordinate.lat == 53.3382


@pytest.mark.parametrize(
    ("lat", "lon"),
    [
        (48.8566, 2.3522),  # Paris: both out of range
        (53.0, 0.0),  # lon east of Ireland
        (60.0, -8.0),  # lat north of Ireland
        (53.0, -20.0),  # mid-Atlantic
    ],
)
def test_coordinate_rejects_points_outside_ireland(lat, lon):
    with pytest.raises(ValidationError):
        Coordinate(lat=lat, lon=lon)


def test_lookup_response_shape():
    response = LookupResponse(
        input=Coordinate(lat=53.3382, lon=-6.2591),
        area=Area(dail_constituency="Dublin South-Central"),
        tds=[Representative(name="Fionn Example", role="TD", email="f@oireachtas.ie")],
        data_last_updated="2026-06-01",
    )
    payload = response.model_dump()
    assert payload["area"] == {"dail_constituency": "Dublin South-Central"}
    assert payload["tds"][0]["party"] is None
    assert "councillors" not in payload


def test_constituency_tds_shape():
    payload = ConstituencyTDs(
        constituency="Mayo",
        tds=[Representative(name="Hugh Placeholder", party="Fianna Fail", role="TD")],
        data_last_updated="2026-06-01",
    ).model_dump()
    assert payload["constituency"] == "Mayo"
    assert payload["tds"][0]["role"] == "TD"
