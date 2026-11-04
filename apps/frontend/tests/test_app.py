from unittest.mock import MagicMock, patch

import pytest
import requests

import app as frontend


@pytest.fixture
def client():
    frontend.app.testing = True
    return frontend.app.test_client()


def test_health(client):
    assert client.get("/healthz").status_code == 200


def test_form_renders(client):
    r = client.get("/")
    assert r.status_code == 200
    assert b"SkyWatch" in r.data


def test_shows_weather(client):
    resp = MagicMock(ok=True, status_code=200)
    resp.json.return_value = {
        "city": "Haifa",
        "country": "Israel",
        "temperature_c": 21.5,
        "conditions": "Overcast",
        "wind_speed_kmh": 12,
        "observed_at": "2026-11-04T10:00",
    }
    with patch.object(frontend.http, "get", return_value=resp):
        r = client.post("/", data={"city": "Haifa"})
    assert b"21.5" in r.data and b"Overcast" in r.data


def test_backend_down(client):
    with patch.object(frontend.http, "get", side_effect=requests.ConnectionError("boom")):
        r = client.post("/", data={"city": "Haifa"})
    assert r.status_code == 200
    assert b"unavailable" in r.data
