"""
Historical Air Quality Data Collector.

Accumulates hourly air quality observations from the Open-Meteo Air Quality API
for the campus coordinates (NMIT, Yelahanka, Bengaluru).
Saves and appends to data/openmeteo_yelahanka_hourly_history.csv, avoiding duplicate timestamps.
"""

import os
from pathlib import Path
from datetime import datetime
import requests
import pandas as pd
import config
from risk_engine import calculate_cpcb_aqi

DATA_DIR = Path("data")
HISTORY_CSV = DATA_DIR / "openmeteo_yelahanka_hourly_history.csv"


def fetch_openmeteo_history(past_days: int = 60) -> pd.DataFrame:
    """Fetch historical hourly air quality data from Open-Meteo."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)

    params = {
        "latitude": config.LATITUDE,
        "longitude": config.LONGITUDE,
        "hourly": "pm2_5,pm10,carbon_monoxide,nitrogen_dioxide,sulphur_dioxide,ozone",
        "past_days": past_days,
        "forecast_days": 1,
        "timezone": "Asia/Kolkata",
    }

    print(f"Fetching {past_days} days of hourly data for {config.LOCATION_NAME} ({config.LATITUDE}, {config.LONGITUDE})...")
    response = requests.get(config.OPEN_METEO_AQ_URL, params=params, timeout=30)
    response.raise_for_status()

    data = response.json()
    hourly = data.get("hourly", {})
    if not hourly or "time" not in hourly:
        raise ValueError("Invalid Open-Meteo response: missing hourly data")

    df = pd.DataFrame(hourly)
    print(f"Fetched {len(df)} hourly observations from API.")
    return df


def update_history_dataset(past_days: int = 60) -> pd.DataFrame:
    """Fetch and merge with existing dataset, ensuring no duplicates."""
    new_df = fetch_openmeteo_history(past_days=past_days)

    if HISTORY_CSV.exists():
        existing_df = pd.read_csv(HISTORY_CSV)
        combined = pd.concat([existing_df, new_df], ignore_index=True)
        combined = combined.drop_duplicates(subset=["time"]).sort_values("time").reset_index(drop=True)
    else:
        combined = new_df.drop_duplicates(subset=["time"]).sort_values("time").reset_index(drop=True)

    retained_columns = [
        "time",
        "pm2_5",
        "pm10",
        "carbon_monoxide",
        "nitrogen_dioxide",
        "sulphur_dioxide",
        "ozone",
    ]
    combined = combined[[column for column in retained_columns if column in combined]]
    combined["cpcb_aqi"] = combined.apply(
        lambda row: calculate_cpcb_aqi(row.get("pm2_5"), row.get("pm10")),
        axis=1,
    )
    combined.to_csv(HISTORY_CSV, index=False)
    print(f"Saved total of {len(combined)} unique hourly records to {HISTORY_CSV}")
    return combined


if __name__ == "__main__":
    df = update_history_dataset(past_days=60)
    print("Sample records:")
    print(df.tail(5))
