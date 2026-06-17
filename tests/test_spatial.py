"""Spatial lookup: known points map to known constituencies."""

import pytest

from irl_reps.spatial import SpatialIndex, load_boundaries

from .conftest import (
    COASTAL_EDGE_POINT,
    DUBLIN_POINT,
    NORTHERN_IRELAND_POINT,
    RURAL_POINT,
)


@pytest.fixture(scope="module")
def index(settings) -> SpatialIndex:
    constituencies = load_boundaries(settings.boundaries_path)
    return SpatialIndex(constituencies)


def test_dublin_point(index):
    lat, lon = DUBLIN_POINT
    constituency = index.locate_constituency(lat, lon)
    assert constituency is not None
    assert constituency.dail_constituency == "Dublin South-Central"


def test_rural_point(index):
    lat, lon = RURAL_POINT
    constituency = index.locate_constituency(lat, lon)
    assert constituency is not None
    assert constituency.dail_constituency == "Mayo"


def test_coastal_edge_point_on_boundary(index):
    """A point exactly on the coastal polygon edge still resolves (intersects)."""
    lat, lon = COASTAL_EDGE_POINT
    constituency = index.locate_constituency(lat, lon)
    assert constituency is not None
    assert constituency.dail_constituency == "Kerry"


def test_uncovered_point_returns_none(index):
    lat, lon = NORTHERN_IRELAND_POINT
    assert index.locate_constituency(lat, lon) is None


def test_open_sea_point_returns_none(index):
    assert index.locate_constituency(53.0, -10.6) is None


def test_constituencies_property_lists_all(index):
    assert index.constituencies == [
        "Dublin South-Central",
        "Galway West",
        "Kerry",
        "Mayo",
    ]
