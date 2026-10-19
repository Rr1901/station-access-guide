import pytest
from fastapi.testclient import TestClient

from app.main import create_app


@pytest.fixture(scope="module")
def client():
    return TestClient(create_app())


def test_health(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["stations"] > 0


def test_get_station_case_insensitive(client):
    resp = client.get("/stations/ndls")
    assert resp.status_code == 200
    assert resp.json()["name"] == "New Delhi"


def test_get_station_not_found(client):
    assert client.get("/stations/ZZZZ").status_code == 404


def test_search_by_name(client):
    names = [s["name"] for s in client.get("/stations", params={"q": "mumbai"}).json()]
    assert names == ["Mumbai Central", "Mumbai Chhatrapati Shivaji Maharaj Terminus"]


def test_search_exact_code_first(client):
    results = client.get("/stations", params={"q": "sc"}).json()
    assert results[0]["code"] == "SC"


def test_filter_by_zone_and_state(client):
    results = client.get("/stations", params={"zone": "cr", "state": "maharashtra"}).json()
    assert {s["code"] for s in results} == {"CSMT", "PUNE"}


def test_nearby(client):
    # Point near Churchgate, Mumbai.
    results = client.get("/stations/nearby", params={"lat": 18.935, "lon": 72.827, "radius_km": 10}).json()
    codes = [r["station"]["code"] for r in results]
    assert codes == ["CSMT", "BCT"]
    assert results[0]["distance_km"] < results[1]["distance_km"]


def test_nearby_validates_input(client):
    assert client.get("/stations/nearby", params={"lat": 100, "lon": 72}).status_code == 422
