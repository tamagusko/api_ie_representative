"""End-to-end API tests against fixture data."""

from .conftest import (
    DUBLIN_POINT,
    LAST_UPDATED,
    NORTHERN_IRELAND_POINT,
    OUTSIDE_BBOX_POINT,
    RURAL_POINT,
)


def test_lookup_get_dublin(client):
    lat, lon = DUBLIN_POINT
    response = client.get("/lookup", params={"lat": lat, "lon": lon})
    assert response.status_code == 200
    body = response.json()
    assert body["input"] == {"lat": lat, "lon": lon}
    assert body["area"] == {"dail_constituency": "Dublin South-Central"}
    assert "councillors" not in body
    assert len(body["tds"]) == 2
    assert all(t["role"] == "TD" for t in body["tds"])
    assert body["data_last_updated"] == LAST_UPDATED


def test_lookup_post_rural(client):
    lat, lon = RURAL_POINT
    response = client.post("/lookup", json={"lat": lat, "lon": lon})
    assert response.status_code == 200
    body = response.json()
    assert body["area"]["dail_constituency"] == "Mayo"
    assert len(body["tds"]) == 1


def test_lookup_outside_ireland_is_422(client):
    lat, lon = OUTSIDE_BBOX_POINT
    response = client.get("/lookup", params={"lat": lat, "lon": lon})
    assert response.status_code == 422
    body = response.json()
    assert body["error"]["code"] == "invalid_coordinates"
    assert "detail" in body["error"]


def test_lookup_malformed_input_is_422(client):
    response = client.get("/lookup", params={"lat": "not-a-number", "lon": -6.25})
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_coordinates"


def test_lookup_uncovered_area_is_404(client):
    lat, lon = NORTHERN_IRELAND_POINT
    response = client.get("/lookup", params={"lat": lat, "lon": lon})
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "area_not_covered"


def test_health(client):
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json() == {"status": "ok", "data_last_updated": LAST_UPDATED}


def test_constituencies_list(client):
    response = client.get("/constituencies")
    assert response.status_code == 200
    body = response.json()
    assert body["constituencies"] == [
        "Dublin South-Central",
        "Galway West",
        "Kerry",
        "Mayo",
    ]
    assert body["data_last_updated"] == LAST_UPDATED


def test_constituency_tds(client):
    response = client.get("/constituencies/Dublin South-Central")
    assert response.status_code == 200
    body = response.json()
    assert body["constituency"] == "Dublin South-Central"
    assert len(body["tds"]) == 2
    assert all(t["role"] == "TD" for t in body["tds"])


def test_constituency_name_is_case_insensitive(client):
    response = client.get("/constituencies/dublin south-central")
    assert response.status_code == 200
    assert response.json()["constituency"] == "Dublin South-Central"


def test_constituency_without_tds_reports_empty(client):
    response = client.get("/constituencies/Galway West")
    assert response.status_code == 200
    assert response.json()["tds"] == []


def test_unknown_constituency_is_404(client):
    response = client.get("/constituencies/Atlantis")
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "unknown_constituency"


def test_index_page_is_served(client):
    response = client.get("/")
    assert response.status_code == 200
    assert "text/html" in response.headers["content-type"]
    assert "Who are my TDs?" in response.text


def test_cors_header_present(client):
    response = client.get("/constituencies", headers={"Origin": "https://collisiontracker.ie"})
    assert response.headers["access-control-allow-origin"] == "*"


def test_boundaries_geojson(client):
    response = client.get("/boundaries")
    assert response.status_code == 200
    assert "geo+json" in response.headers["content-type"]
    body = response.json()
    assert body["type"] == "FeatureCollection"
    names = {f["properties"]["name"] for f in body["features"]}
    assert "Dublin South-Central" in names
    assert "Mayo" in names
