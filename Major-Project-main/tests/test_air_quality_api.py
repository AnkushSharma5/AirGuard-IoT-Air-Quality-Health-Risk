"""
Tests for air_quality_api.py

Covers:
  • Valid API response parsing
  • Missing / null fields in response
  • Malformed (non-JSON) response
  • HTTP error responses (4xx, 5xx)
  • Request timeout
  • Network disconnection
  • Cache freshness / staleness
  • Unavailable status when no cache exists
"""

import time
import json
import pytest
from unittest.mock import patch, MagicMock
import requests

# Reset the module cache before each test
import air_quality_api


# ── Fixtures ─────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def reset_cache():
    """Clear the module-level cache before each test."""
    air_quality_api._cache["data"] = None
    air_quality_api._cache["fetched_at"] = 0
    air_quality_api._cache["last_error"] = None
    yield


def _make_valid_response():
    """Return a realistic Open-Meteo API response dict."""
    return {
        "current": {
            "time": "2025-06-15T14:00",
            "pm2_5": 35.2,
            "pm10": 58.7,
        },
        "hourly": {
            "time": [
                "2025-06-15T14:00",
                "2025-06-15T15:00",
                "2025-06-15T16:00",
                "2025-06-15T17:00",
                "2025-06-15T18:00",
                "2025-06-15T19:00",
            ],
            "pm2_5": [35.2, 33.1, 31.0, 29.5, 28.0, 27.2],
            "pm10": [58.7, 55.3, 52.1, 49.8, 47.5, 46.0],
        },
    }


def _mock_get_success(url, **kwargs):
    """Simulate a successful API call."""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = _make_valid_response()
    resp.raise_for_status = MagicMock()
    return resp


# ── Test: Valid response ─────────────────────────────────────────────

@patch("air_quality_api.requests.get", side_effect=_mock_get_success)
def test_valid_response_parses_current(mock_get):
    result = air_quality_api.get_air_quality()

    assert result["status"] == "ok"
    assert result["current"]["pm2_5"] == 35.2
    assert result["current"]["pm10"] == 58.7
    assert result["current"]["cpcb_aqi"] == 59
    assert result["current"]["time"] == "2025-06-15T14:00"


@patch("air_quality_api.requests.get", side_effect=_mock_get_success)
def test_valid_response_parses_forecast(mock_get):
    result = air_quality_api.get_air_quality()

    assert result["forecast"] is not None
    assert len(result["forecast"]) == 6
    assert result["forecast"][0]["pm2_5"] == 35.2
    assert result["forecast"][5]["cpcb_aqi"] == 46


@patch("air_quality_api.requests.get", side_effect=_mock_get_success)
def test_valid_response_metadata(mock_get):
    result = air_quality_api.get_air_quality()

    assert result["source"] == "Open-Meteo Air Quality API (model estimate)"
    assert result["index_system"] == "CPCB AQI estimate (PM2.5 and PM10)"
    assert "not an official CPCB reading" in result["methodology_note"]
    assert result["fetched_at"] is not None
    assert result["error"] is None or "error" not in result


# ── Test: Missing fields ─────────────────────────────────────────────

@patch("air_quality_api.requests.get")
def test_missing_current_fields(mock_get):
    """API returns current block but some fields are null."""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "current": {"time": "2025-06-15T14:00", "pm2_5": None, "pm10": 58.7},
        "hourly": {"time": [], "pm2_5": [], "pm10": []},
    }
    resp.raise_for_status = MagicMock()
    mock_get.return_value = resp

    result = air_quality_api.get_air_quality()
    assert result["status"] == "ok"
    assert result["current"]["pm2_5"] is None
    assert result["current"]["pm10"] == 58.7
    assert result["current"]["cpcb_aqi"] == 59


@patch("air_quality_api.requests.get")
def test_missing_current_block(mock_get):
    """API response has no 'current' key at all."""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "hourly": {"time": [], "pm2_5": [], "pm10": []},
    }
    resp.raise_for_status = MagicMock()
    mock_get.return_value = resp

    result = air_quality_api.get_air_quality()
    assert result["status"] == "ok"
    assert result["current"]["pm2_5"] is None
    assert result["current"]["pm10"] is None
    assert result["current"]["cpcb_aqi"] is None


@patch("air_quality_api.requests.get")
def test_missing_hourly_block(mock_get):
    """API response has no 'hourly' key at all."""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = {
        "current": {"time": "2025-06-15T14:00", "pm2_5": 35.2, "pm10": 58.7},
    }
    resp.raise_for_status = MagicMock()
    mock_get.return_value = resp

    result = air_quality_api.get_air_quality()
    assert result["status"] == "ok"
    assert result["forecast"] == []


# ── Test: Malformed response ─────────────────────────────────────────

@patch("air_quality_api.requests.get")
def test_malformed_json_response(mock_get):
    """API returns something that is not a dict."""
    resp = MagicMock()
    resp.status_code = 200
    resp.json.return_value = "not a dict"
    resp.raise_for_status = MagicMock()
    mock_get.return_value = resp

    result = air_quality_api.get_air_quality()
    assert result["status"] == "unavailable"
    assert result["current"] is None


# ── Test: HTTP errors ────────────────────────────────────────────────

@patch("air_quality_api.requests.get")
def test_http_500_error(mock_get):
    """Server returns 500."""
    resp = MagicMock()
    resp.status_code = 500
    resp.raise_for_status.side_effect = requests.HTTPError("500 Server Error")
    mock_get.return_value = resp

    result = air_quality_api.get_air_quality()
    assert result["status"] == "unavailable"
    assert "500" in result["error"]


@patch("air_quality_api.requests.get")
def test_http_404_error(mock_get):
    """Endpoint not found."""
    resp = MagicMock()
    resp.status_code = 404
    resp.raise_for_status.side_effect = requests.HTTPError("404 Not Found")
    mock_get.return_value = resp

    result = air_quality_api.get_air_quality()
    assert result["status"] == "unavailable"


# ── Test: Timeout ────────────────────────────────────────────────────

@patch("air_quality_api.requests.get",
       side_effect=requests.Timeout("Connection timed out"))
def test_timeout(mock_get):
    result = air_quality_api.get_air_quality()
    assert result["status"] == "unavailable"
    assert "timed out" in result["error"].lower()


# ── Test: Network disconnection ──────────────────────────────────────

@patch("air_quality_api.requests.get",
       side_effect=requests.ConnectionError("No network"))
def test_connection_error(mock_get):
    result = air_quality_api.get_air_quality()
    assert result["status"] == "unavailable"
    assert result["current"] is None


# ── Test: Cache behaviour ────────────────────────────────────────────

@patch("air_quality_api.requests.get", side_effect=_mock_get_success)
def test_cache_returns_cached_data(mock_get):
    """Second call within TTL should return cached data without API call."""
    first = air_quality_api.get_air_quality()
    assert mock_get.call_count == 1

    second = air_quality_api.get_air_quality()
    assert mock_get.call_count == 1  # no second API call
    assert second["status"] == "ok"


@patch("air_quality_api.requests.get")
def test_stale_cache_on_api_failure(mock_get):
    """If cache exists but API fails, return stale data."""
    # First call succeeds
    mock_get.side_effect = _mock_get_success
    air_quality_api.get_air_quality()

    # Force cache to be old
    air_quality_api._cache["fetched_at"] = time.time() - 9999

    # Second call fails
    mock_get.side_effect = requests.ConnectionError("Network down")
    result = air_quality_api.get_air_quality()

    assert result["status"] == "stale"
    assert result["current"]["pm2_5"] == 35.2  # old data still there
    assert result["error"] is not None


# ── Test: Unavailable when no cache and API fails ────────────────────

@patch("air_quality_api.requests.get",
       side_effect=requests.ConnectionError("No network"))
def test_unavailable_no_cache(mock_get):
    result = air_quality_api.get_air_quality()
    assert result["status"] == "unavailable"
    assert result["current"] is None
    assert result["forecast"] is None


# ── Test: Cache info ─────────────────────────────────────────────────

def test_cache_info_empty():
    info = air_quality_api.get_cache_info()
    assert info["has_data"] is False
    assert info["fetched_at"] is None
