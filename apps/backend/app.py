"""SkyWatch backend: resolves a city with Open-Meteo geocoding and returns current weather."""

import logging
import os

import requests
from flask import Flask, jsonify, request

GEOCODING_URL = os.getenv("GEOCODING_URL", "https://geocoding-api.open-meteo.com/v1/search")
FORECAST_URL = os.getenv("FORECAST_URL", "https://api.open-meteo.com/v1/forecast")
HTTP_TIMEOUT = float(os.getenv("HTTP_TIMEOUT_SECONDS", "5"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

# WMO weather interpretation codes, as documented by Open-Meteo.
WEATHER_CODES = {
    0: "Clear sky",
    1: "Mainly clear",
    2: "Partly cloudy",
    3: "Overcast",
    45: "Fog",
    48: "Depositing rime fog",
    51: "Light drizzle",
    53: "Moderate drizzle",
    55: "Dense drizzle",
    56: "Light freezing drizzle",
    57: "Dense freezing drizzle",
    61: "Slight rain",
    63: "Moderate rain",
    65: "Heavy rain",
    66: "Light freezing rain",
    67: "Heavy freezing rain",
    71: "Slight snow",
    73: "Moderate snow",
    75: "Heavy snow",
    77: "Snow grains",
    80: "Slight rain showers",
    81: "Moderate rain showers",
    82: "Violent rain showers",
    85: "Slight snow showers",
    86: "Heavy snow showers",
    95: "Thunderstorm",
    96: "Thunderstorm with slight hail",
    99: "Thunderstorm with heavy hail",
}

logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("backend")

app = Flask(__name__)
http = requests.Session()


class UpstreamError(Exception):
    """Open-Meteo was unreachable or returned an error."""


def geocode(city: str) -> dict | None:
    try:
        resp = http.get(
            GEOCODING_URL,
            params={"name": city, "count": 1, "language": "en", "format": "json"},
            timeout=HTTP_TIMEOUT,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise UpstreamError(f"geocoding failed: {exc}") from exc
    results = resp.json().get("results") or []
    return results[0] if results else None


def current_weather(lat: float, lon: float) -> dict:
    try:
        resp = http.get(
            FORECAST_URL,
            params={
                "latitude": lat,
                "longitude": lon,
                "current": "temperature_2m,weather_code,wind_speed_10m",
            },
            timeout=HTTP_TIMEOUT,
        )
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise UpstreamError(f"forecast failed: {exc}") from exc
    return resp.json()["current"]


@app.get("/api/weather")
def weather():
    city = (request.args.get("city") or "").strip()
    if not city:
        return jsonify(error="query parameter 'city' is required"), 400

    try:
        place = geocode(city)
        if place is None:
            return jsonify(error=f"city '{city}' not found"), 404
        current = current_weather(place["latitude"], place["longitude"])
    except UpstreamError as exc:
        log.warning("upstream error for city=%s: %s", city, exc)
        return jsonify(error="weather provider unavailable"), 502

    code = current.get("weather_code")
    return jsonify(
        city=place.get("name"),
        country=place.get("country"),
        latitude=place["latitude"],
        longitude=place["longitude"],
        temperature_c=current.get("temperature_2m"),
        wind_speed_kmh=current.get("wind_speed_10m"),
        weather_code=code,
        conditions=WEATHER_CODES.get(code, "Unknown"),
        observed_at=current.get("time"),
    )


@app.get("/healthz")
def healthz():
    """Liveness: the process is up and serving requests."""
    return jsonify(status="ok")


@app.get("/readyz")
def readyz():
    """Readiness: ready to take traffic. Deliberately does not call Open-Meteo,
    so an external outage does not pull every pod out of the Service."""
    return jsonify(status="ready")
