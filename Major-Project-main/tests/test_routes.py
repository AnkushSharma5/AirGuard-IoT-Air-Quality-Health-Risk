"""
Integration and functional tests for Flask endpoints (app.py).

Covers:
- GET / (HTML template rendering)
- GET /api/current (JSON structure and fields)
- GET /api/forecast (Baseline + ML overlays)
- GET /api/history (ThingSpeak historical feeds)
- POST /api/health-risk (Health profile advisory evaluation)
- GET /api/models (Empirical benchmarks and metrics)
- GET /api/status (System diagnostic status)
"""

import pytest
from app import app


@pytest.fixture
def client():
    app.config["TESTING"] = True
    with app.test_client() as client:
        yield client


def test_index_route(client):
    response = client.get("/")
    assert response.status_code == 200
    html = response.data.decode("utf-8")
    assert "AirGuard IoT" in html
    assert "CPCB Air Quality Index" in html
    assert "not an official CPCB reading" in html
    assert "Educational Prototype" in html


def test_api_current_route(client):
    response = client.get("/api/current")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ok"
    assert "sensor_telemetry" in data
    assert "open_meteo" in data
    assert "default_risk_advisory" in data
    assert "ml_category_prediction" in data


def test_api_forecast_route(client):
    response = client.get("/api/forecast")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ok"
    assert "baseline_forecast" in data
    assert "ml_forecast" in data
    assert len(data["ml_forecast"]["forecast"]) == 6


def test_api_history_route(client):
    response = client.get("/api/history?limit=10")
    assert response.status_code == 200
    data = response.get_json()
    assert "status" in data
    assert "feeds" in data


def test_api_health_risk_post(client):
    payload = {
        "profile_id": "asthma",
        "activity_level": "outdoor_exercise",
    }
    response = client.post("/api/health-risk", json=payload)
    assert response.status_code == 200
    data = response.get_json()
    assert "risk_level" in data
    assert "tailored_precautions" in data
    assert data["profile"]["id"] == "asthma"
    assert data["activity_level"] == "outdoor_exercise"
    assert "disclaimer" in data


def test_api_models_route(client):
    response = client.get("/api/models")
    assert response.status_code == 200
    data = response.get_json()
    assert data["status"] == "ok"
    assert "forecasting_evaluation" in data
    assert "classification_evaluation" in data


def test_api_status_route(client):
    response = client.get("/api/status")
    assert response.status_code == 200
    data = response.get_json()
    assert data["system"] == "IoT Air Quality & Risk Advisory System"
    assert "thingspeak_configured" in data
