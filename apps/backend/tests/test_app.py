from unittest.mock import MagicMock, patch

import pytest
import requests

import app as backend


@pytest.fixture
def client():
    backend.app.testing = True
    return backend.app.test_client()


def _resp(payload):
    r = MagicMock()
    r.json.return_value = payload
    r.raise_for_status.return_value = None
    return r


def test_health(client):
    assert client.get("/healthz").status_code == 200
    assert client.get("/readyz").status_code == 200


def test_missing_city(client):
    assert client.get("/api/weather").status_code == 400


def test_weather_ok(client):
    geo = {"results": [{"name": "Tel Aviv", "country": "Israel", "latitude": 32.08, "longitude": 34.78}]}
    fc = {"current": {"time": "2026-11-04T10:00", "temperature_2m": 24.3, "weather_code": 1, "wind_speed_10m": 9.1}}
    with patch.object(backend.http, "get", side_effect=[_resp(geo), _resp(fc)]):
        r = client.get("/api/weather?city=Tel%20Aviv")
    assert r.status_code == 200
    body = r.get_json()
    assert body["city"] == "Tel Aviv"
    assert body["temperature_c"] == 24.3
    assert body["conditions"] == "Mainly clear"


def test_city_not_found(client):
    with patch.object(backend.http, "get", return_value=_resp({})):
        assert client.get("/api/weather?city=Nowhereville").status_code == 404


def test_upstream_down(client):
    with patch.object(backend.http, "get", side_effect=requests.ConnectionError("boom")):
        assert client.get("/api/weather?city=Haifa").status_code == 502
