"""SkyWatch frontend: a city form that calls the backend API and renders the result."""

import logging
import os

import requests
from flask import Flask, jsonify, render_template, request

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000").rstrip("/")
HTTP_TIMEOUT = float(os.getenv("HTTP_TIMEOUT_SECONDS", "10"))
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")

logging.basicConfig(level=LOG_LEVEL, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("frontend")

app = Flask(__name__)
http = requests.Session()


@app.route("/", methods=["GET", "POST"])
def index():
    city = ""
    result = None
    error = None

    if request.method == "POST":
        city = (request.form.get("city") or "").strip()
        if not city:
            error = "Please enter a city name."
        else:
            try:
                resp = http.get(f"{BACKEND_URL}/api/weather", params={"city": city}, timeout=HTTP_TIMEOUT)
                body = resp.json()
                if resp.ok:
                    result = body
                else:
                    error = body.get("error", f"Backend returned {resp.status_code}")
            except (requests.RequestException, ValueError) as exc:
                log.warning("backend call failed: %s", exc)
                error = "The weather service is unavailable right now. Please try again."

    return render_template("index.html", city=city, result=result, error=error)


@app.get("/healthz")
def healthz():
    return jsonify(status="ok")
