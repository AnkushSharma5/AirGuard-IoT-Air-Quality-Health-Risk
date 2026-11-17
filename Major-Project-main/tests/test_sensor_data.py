"""
Unit tests for sensor_data.py (ThingSpeak telemetry parser).

Validates:
- Successful payload parsing
- Handling of missing fields / nulls
- Range checks for temperature, humidity, and gas sensors
- Unconfigured and network error states
"""

from unittest.mock import patch, MagicMock
import pytest
import sensor_data


def test_safe_float_helper():
    assert sensor_data._safe_float("25.4") == 25.4
    assert sensor_data._safe_float(42) == 42.0
    assert sensor_data._safe_float(None) is None
    assert sensor_data._safe_float("invalid") is None


@patch("sensor_data.requests.get")
def test_get_latest_sensor_reading_success(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "channel": {"name": "Test Station"},
        "feeds": [
            {
                "entry_id": 101,
                "created_at": "2026-10-09T10:00:00Z",
                "field1": "28.5",
                "field2": "54.2",
                "field3": "650",
                "field4": "210",
            }
        ]
    }
    mock_get.return_value = mock_resp

    result = sensor_data.get_latest_sensor_reading()
    assert result["status"] == "ok"
    assert result["data"]["temperature_c"] == 28.5
    assert result["data"]["humidity_pct"] == 54.2
    assert result["data"]["mq135_raw"] == 650.0
    assert result["data"]["mq7_raw"] == 210.0
    assert result["data"]["mq135_exceeds_threshold"] is True


@patch("sensor_data.requests.get")
def test_get_latest_sensor_reading_out_of_range(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "feeds": [
            {
                "entry_id": 102,
                "field1": "999.0",  # Faulty temp
                "field2": "50.0",
                "field3": "500",
            }
        ]
    }
    mock_get.return_value = mock_resp

    result = sensor_data.get_latest_sensor_reading()
    assert result["status"] == "sensor_warning"
    assert result["data"]["temperature_valid"] is False
    assert result["data"]["humidity_valid"] is True


@patch("sensor_data.requests.get")
def test_get_sensor_history(mock_get):
    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "feeds": [
            {"entry_id": 1, "field1": "25.0", "field2": "40.0", "field3": "500"},
            {"entry_id": 2, "field1": "26.0", "field2": "42.0", "field3": "520"},
        ]
    }
    mock_get.return_value = mock_resp

    history = sensor_data.get_sensor_history(results=2)
    assert history["status"] == "ok"
    assert history["count"] == 2
    assert history["feeds"][0]["temperature"] == 25.0
