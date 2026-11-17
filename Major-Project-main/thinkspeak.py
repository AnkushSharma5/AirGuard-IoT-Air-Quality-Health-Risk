"""
Quick test script: fetch the latest reading from ThingSpeak.

Reads credentials from config.py / .env — no secrets in this file.
Run:  python thinkspeak.py
"""

import requests
import config

if not config.THINGSPEAK_CHANNEL_ID or not config.THINGSPEAK_READ_API_KEY:
    print("ERROR: ThingSpeak credentials not set.")
    print("Copy .env.example to .env and fill in your values.")
    raise SystemExit(1)

url = (
    f"{config.THINGSPEAK_BASE_URL}/channels/"
    f"{config.THINGSPEAK_CHANNEL_ID}/feeds/last.json"
)

response = requests.get(
    url,
    params={"api_key": config.THINGSPEAK_READ_API_KEY},
    timeout=10,
)

if response.status_code == 200:
    data = response.json()

    temperature = float(data["field1"])
    humidity = float(data["field2"])
    mq135 = float(data["field3"])

    print("\n===== LIVE AIR QUALITY DATA =====")
    print(f"Temperature : {temperature} °C")
    print(f"Humidity    : {humidity} %")
    print(f"MQ135 (raw) : {mq135}")
    print("=================================")
else:
    print("Failed to get data from ThingSpeak")
    print("Status code:", response.status_code)