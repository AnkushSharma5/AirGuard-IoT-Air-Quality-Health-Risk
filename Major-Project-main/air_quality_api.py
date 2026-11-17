"""
Open-Meteo Air Quality API integration.

Fetches current and forecast PM2.5 and PM10 for the
configured location.  Results are model-based ESTIMATES, not local
sensor measurements.

Features:
  • In-memory cache with configurable TTL (default 10 min)
  • Safe JSON parsing — never crashes on missing fields
  • HTTP timeout + error handling
  • "stale" / "unavailable" status for the frontend
  • Stores last-successful-update time
"""

import time
import logging
from datetime import datetime, timezone, timedelta

import requests
import config
from risk_engine import calculate_cpcb_aqi

logger = logging.getLogger(__name__)

# ── Module-level cache ───────────────────────────────────────────────
_cache = {
    "data": None,           # last successful parsed result
    "fetched_at": 0,        # time.time() of last successful fetch
    "last_error": None,     # last error message (str or None)
}

# IST timezone offset
IST = timezone(timedelta(hours=5, minutes=30))


# ── Public API ───────────────────────────────────────────────────────

def get_air_quality():
    """Return cached or freshly-fetched air quality data.

    Returns a dict with:
        status        : "ok" | "stale" | "unavailable"
        source        : "Open-Meteo Air Quality API (model estimate)"
        index_system  : "CPCB AQI estimate (PM2.5 and PM10)"
        fetched_at    : ISO timestamp of last successful fetch (or None)
        stale_seconds : seconds since last successful fetch (or None)
        error         : last error message (or None)
        current       : {pm2_5, pm10, cpcb_aqi, time} or None
        forecast      : [{time, pm2_5, pm10, cpcb_aqi}, ...] or None

    Never raises; all errors are caught and reflected in `status`.
    """
    now = time.time()
    age = now - _cache["fetched_at"] if _cache["fetched_at"] else None

    # Return cache if still fresh
    if _cache["data"] and age is not None and age < config.OPEN_METEO_CACHE_SECONDS:
        result = _cache["data"].copy()
        result["status"] = "ok"
        result["stale_seconds"] = int(age)
        return result

    # Try to fetch fresh data
    try:
        fresh = _fetch_from_api()
        _cache["data"] = fresh
        _cache["fetched_at"] = now
        _cache["last_error"] = None

        result = fresh.copy()
        result["status"] = "ok"
        result["stale_seconds"] = 0
        return result

    except Exception as exc:
        error_msg = str(exc)
        _cache["last_error"] = error_msg
        logger.warning("Open-Meteo fetch failed: %s", error_msg)

        # Return stale cache if available
        if _cache["data"]:
            result = _cache["data"].copy()
            result["status"] = "stale"
            result["stale_seconds"] = int(now - _cache["fetched_at"]) if _cache["fetched_at"] else None
            result["error"] = error_msg
            return result

        # No cache at all
        return _unavailable_response(error_msg)


def get_cache_info():
    """Return cache diagnostic info (for status endpoints)."""
    return {
        "has_data": _cache["data"] is not None,
        "fetched_at": (
            datetime.fromtimestamp(_cache["fetched_at"], tz=IST).isoformat()
            if _cache["fetched_at"]
            else None
        ),
        "age_seconds": (
            int(time.time() - _cache["fetched_at"])
            if _cache["fetched_at"]
            else None
        ),
        "last_error": _cache["last_error"],
        "cache_ttl_seconds": config.OPEN_METEO_CACHE_SECONDS,
    }


# ── Internal helpers ─────────────────────────────────────────────────

def _fetch_from_api():
    """Make a real HTTP call to Open-Meteo and parse the response.

    Raises on HTTP errors, timeouts, or malformed data.
    """
    params = {
        "latitude": config.LATITUDE,
        "longitude": config.LONGITUDE,
        "current": "pm2_5,pm10",
        "hourly": "pm2_5,pm10",
        "timezone": "Asia/Kolkata",
        "forecast_hours": config.OPEN_METEO_FORECAST_HOURS,
    }

    response = requests.get(
        config.OPEN_METEO_AQ_URL,
        params=params,
        timeout=config.OPEN_METEO_TIMEOUT_SECONDS,
    )
    response.raise_for_status()

    raw = response.json()

    if not isinstance(raw, dict):
        raise ValueError("API returned non-dict response")

    return _parse_response(raw)


def _parse_response(raw):
    """Parse the Open-Meteo JSON into our standardised format.

    Handles missing fields gracefully — any missing value becomes None
    rather than crashing.
    """
    # --- Current values ---
    current_raw = raw.get("current") or {}
    pm2_5 = _safe_float(current_raw.get("pm2_5"))
    pm10 = _safe_float(current_raw.get("pm10"))
    current = {
        "pm2_5": pm2_5,
        "pm10": pm10,
        "cpcb_aqi": calculate_cpcb_aqi(pm2_5=pm2_5, pm10=pm10),
        "time": current_raw.get("time"),
    }

    # --- Hourly forecast ---
    hourly_raw = raw.get("hourly") or {}
    times = hourly_raw.get("time") or []
    pm2_5_list = hourly_raw.get("pm2_5") or []
    pm10_list = hourly_raw.get("pm10") or []

    max_len = len(times)
    forecast = []
    for i in range(max_len):
        pm2_5 = _safe_float(pm2_5_list[i]) if i < len(pm2_5_list) else None
        pm10 = _safe_float(pm10_list[i]) if i < len(pm10_list) else None
        forecast.append({
            "time": times[i] if i < len(times) else None,
            "pm2_5": pm2_5,
            "pm10": pm10,
            "cpcb_aqi": calculate_cpcb_aqi(pm2_5=pm2_5, pm10=pm10),
        })

    now_ist = datetime.now(IST).isoformat()

    return {
        "source": "Open-Meteo Air Quality API (model estimate)",
        "index_system": "CPCB AQI estimate (PM2.5 and PM10)",
        "methodology_note": (
            "Indicative estimate from hourly modelled PM2.5 and PM10 using CPCB "
            "breakpoints; it is not an official CPCB reading or a 24-hour average."
        ),
        "fetched_at": now_ist,
        "error": None,
        "current": current,
        "forecast": forecast,
    }


def _unavailable_response(error=None):
    """Return a safe 'no data available' dict."""
    return {
        "status": "unavailable",
        "source": "Open-Meteo Air Quality API (model estimate)",
        "index_system": "CPCB AQI estimate (PM2.5 and PM10)",
        "methodology_note": (
            "Indicative estimate from hourly modelled PM2.5 and PM10 using CPCB "
            "breakpoints; it is not an official CPCB reading or a 24-hour average."
        ),
        "fetched_at": None,
        "stale_seconds": None,
        "error": error,
        "current": None,
        "forecast": None,
    }


def _safe_float(value):
    """Convert to float, returning None for anything invalid."""
    if value is None:
        return None
    try:
        result = float(value)
        return result
    except (ValueError, TypeError):
        return None


def _safe_int(value):
    """Convert to int, returning None for anything invalid."""
    if value is None:
        return None
    try:
        result = int(float(value))
        return result
    except (ValueError, TypeError):
        return None
