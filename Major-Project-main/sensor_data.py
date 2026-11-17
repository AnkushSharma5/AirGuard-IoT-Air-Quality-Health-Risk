"""
ThingSpeak Local IoT Sensor Data Reader Module.

Reads live and historical telemetry published by the ESP32 to ThingSpeak:
- field1: Ambient Temperature (°C)
- field2: Relative Humidity (%)
- field3: MQ-135 Raw ADC Gas Sensor Response
- field4: MQ-7 Raw ADC Gas Sensor Response (if hardware equipped)

Design Rules:
1. Labeling: Strictly labels all readings as "MEASURED (Local IoT Sensors)".
2. MQ-135 and MQ-7 values are raw analog ADC voltages (0-4095),
   NEVER converted or misrepresented as PM2.5, PM10, or calibrated AQI.
3. Fault Detection: Catches NaN, out-of-range, and stale readings.
4. Error Handling: Timeouts, network failures, or unconfigured credentials
   return clean status objects without crashing the Flask backend.
"""

from datetime import datetime, timezone
from typing import Dict, Any, List, Optional
import requests
import config

try:
    from zoneinfo import ZoneInfo
    IST = ZoneInfo("Asia/Kolkata")
except Exception:
    IST = timezone.utc


def _safe_float(val: Any) -> Optional[float]:
    if val is None or val == "":
        return None
    try:
        f = float(val)
        return round(f, 2)
    except (ValueError, TypeError):
        return None


def get_latest_sensor_reading() -> Dict[str, Any]:
    """Fetch the latest telemetry record from ThingSpeak channel."""
    if not config.THINGSPEAK_CHANNEL_ID or not config.THINGSPEAK_READ_API_KEY:
        return {
            "status": "unconfigured",
            "source": "MEASURED (Local IoT Sensors)",
            "message": "ThingSpeak credentials not configured in environment.",
            "data": None,
        }

    url = f"https://api.thingspeak.com/channels/{config.THINGSPEAK_CHANNEL_ID}/feeds.json"
    params = {
        "api_key": config.THINGSPEAK_READ_API_KEY,
        "results": 1,
    }

    try:
        response = requests.get(url, params=params, timeout=8)
        response.raise_for_status()
        payload = response.json()
        feeds = payload.get("feeds", [])

        if not feeds:
            return {
                "status": "empty",
                "source": "MEASURED (Local IoT Sensors)",
                "message": "Channel is accessible but contains no feeds yet.",
                "data": None,
            }

        latest = feeds[-1]
        temp = _safe_float(latest.get("field1"))
        hum = _safe_float(latest.get("field2"))
        mq135_raw = _safe_float(latest.get("field3"))
        mq7_raw = _safe_float(latest.get("field4"))
        timestamp = latest.get("created_at")

        # Basic range and validity checks
        temp_valid = temp is not None and -10.0 <= temp <= 65.0
        hum_valid = hum is not None and 0.0 <= hum <= 100.0
        mq135_valid = mq135_raw is not None and 0.0 <= mq135_raw <= 4095.0
        mq7_valid = mq7_raw is not None and 0.0 <= mq7_raw <= 4095.0

        is_all_valid = temp_valid and hum_valid and mq135_valid

        return {
            "status": "ok" if is_all_valid else "sensor_warning",
            "source": "MEASURED (Local IoT Sensors)",
            "entry_id": latest.get("entry_id"),
            "timestamp": timestamp,
            "data": {
                "temperature_c": temp,
                "temperature_valid": temp_valid,
                "humidity_pct": hum,
                "humidity_valid": hum_valid,
                "mq135_raw": mq135_raw,
                "mq135_valid": mq135_valid,
                "mq135_exceeds_threshold": (mq135_raw > config.MQ135_THRESHOLD) if mq135_raw is not None else False,
                "mq7_raw": mq7_raw,
                "mq7_valid": mq7_valid,
            },
            "channel_title": payload.get("channel", {}).get("name", "Air Quality Station"),
        }

    except requests.exceptions.Timeout:
        return {
            "status": "timeout",
            "source": "MEASURED (Local IoT Sensors)",
            "message": "ThingSpeak API request timed out.",
            "data": None,
        }
    except requests.exceptions.RequestException as e:
        return {
            "status": "network_error",
            "source": "MEASURED (Local IoT Sensors)",
            "message": f"ThingSpeak network communication failure: {str(e)}",
            "data": None,
        }
    except Exception as e:
        return {
            "status": "error",
            "source": "MEASURED (Local IoT Sensors)",
            "message": f"Unexpected error reading sensor telemetry: {str(e)}",
            "data": None,
        }


def get_sensor_history(results: int = 50) -> Dict[str, Any]:
    """Fetch historical telemetry feeds for dashboard charting and analysis."""
    if not config.THINGSPEAK_CHANNEL_ID or not config.THINGSPEAK_READ_API_KEY:
        return {
            "status": "unconfigured",
            "source": "MEASURED (Local IoT Sensors)",
            "feeds": [],
        }

    results = min(max(5, results), 100)
    url = f"https://api.thingspeak.com/channels/{config.THINGSPEAK_CHANNEL_ID}/feeds.json"
    params = {
        "api_key": config.THINGSPEAK_READ_API_KEY,
        "results": results,
    }

    try:
        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()
        payload = response.json()
        raw_feeds = payload.get("feeds", [])

        parsed_feeds = []
        for f in raw_feeds:
            parsed_feeds.append({
                "entry_id": f.get("entry_id"),
                "timestamp": f.get("created_at"),
                "temperature": _safe_float(f.get("field1")),
                "humidity": _safe_float(f.get("field2")),
                "mq135_raw": _safe_float(f.get("field3")),
                "mq7_raw": _safe_float(f.get("field4")),
            })

        return {
            "status": "ok",
            "source": "MEASURED (Local IoT Sensors)",
            "count": len(parsed_feeds),
            "feeds": parsed_feeds,
        }
    except Exception as e:
        return {
            "status": "error",
            "source": "MEASURED (Local IoT Sensors)",
            "message": str(e),
            "feeds": [],
        }
