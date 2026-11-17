"""
Centralised configuration for the Air Quality Monitoring project.

All settings live here. Secrets (API keys, passwords) are loaded from
a .env file and are NEVER hard-coded. Copy .env.example to .env and
fill in your real values before running.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# ── Load .env if present ─────────────────────────────────────────────
BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

# ── ThingSpeak ───────────────────────────────────────────────────────
THINGSPEAK_CHANNEL_ID = os.getenv("THINGSPEAK_CHANNEL_ID", "")
THINGSPEAK_READ_API_KEY = os.getenv("THINGSPEAK_READ_API_KEY", "")

# ThingSpeak field mapping (matches ESP32 sketch)
#   field1 = Temperature (°C)
#   field2 = Humidity (%)
#   field3 = MQ-135 raw ADC
#   field4 = MQ-7 raw ADC (if configured)
THINGSPEAK_BASE_URL = "https://api.thingspeak.com"

# ── Sensor location (NMIT, Yelahanka, Bengaluru) ────────────────────
LATITUDE = float(os.getenv("LATITUDE", "13.1291"))
LONGITUDE = float(os.getenv("LONGITUDE", "77.5865"))
LOCATION_NAME = os.getenv("LOCATION_NAME", "NMIT, Yelahanka, Bengaluru")

# ── Open-Meteo Air Quality API ───────────────────────────────────────
# Free API — no key needed. Returns model-based estimates, NOT
# local sensor measurements.
OPEN_METEO_AQ_URL = "https://air-quality-api.open-meteo.com/v1/air-quality"
OPEN_METEO_TIMEOUT_SECONDS = 10
OPEN_METEO_CACHE_SECONDS = int(os.getenv("OPEN_METEO_CACHE_SECONDS", "600"))  # 10 min
OPEN_METEO_FORECAST_HOURS = 6

# ── MQ-135 provisional threshold ────────────────────────────────────
# This is a raw ADC comparison value, NOT an official AQI or ppm
# threshold. Used only for a simple high/low sensor-response label.
MQ135_THRESHOLD = int(os.getenv("MQ135_THRESHOLD", "600"))

# ── Flask ────────────────────────────────────────────────────────────
FLASK_DEBUG = os.getenv("FLASK_DEBUG", "false").lower() in ("true", "1", "yes")
FLASK_HOST = os.getenv("FLASK_HOST", "127.0.0.1")
FLASK_PORT = int(os.getenv("FLASK_PORT", "5000"))

# ── Model paths ──────────────────────────────────────────────────────
MODELS_DIR = BASE_DIR / "models"
ML_RESULTS_FILE = MODELS_DIR / "evaluation_results.json"

# ── Data paths ───────────────────────────────────────────────────────
DATA_DIR = BASE_DIR / "data"
