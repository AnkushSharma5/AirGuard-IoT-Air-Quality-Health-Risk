# AirGuard: Cost-Effective IoT Framework for Air Quality Monitoring & Health Risk Advisory

**Department of Information Science & Engineering | B.Tech Major Project**  
**Institution:** Nitte Meenakshi Institute of Technology (NMIT), Yelahanka, Bengaluru  

[![Python Tests](https://img.shields.io/badge/pytest-CPCB%20AQI-10b981.svg)]()
[![Flask Version](https://img.shields.io/badge/Flask-3.1.3-blue.svg)]()
[![Hardware](https://img.shields.io/badge/Hardware-ESP32%20%7C%20DHT11%20%7C%20MQ--135%20%7C%20MQ--7-purple.svg)]()
[![License](https://img.shields.io/badge/Status-BTech%20Verified-emerald.svg)]()

---

## 1. Project Overview & Abstract

Rapid urban industrialization and vehicular emissions have made ambient air pollution a primary public health concern. Conventional regulatory continuous air quality monitoring stations (CAAQMS) are high-cost, fixed, and sparse.

**AirGuard** presents a cost-effective, dual-tier Internet of Things (IoT) and Machine Learning framework:
1. **Edge Sensing Tier:** An ESP32 microcontroller acquiring real-time ambient temperature and humidity (DHT11), general reducing gases/air quality (MQ-135), and carbon monoxide response (MQ-7), streaming to ThingSpeak cloud telemetry and a local rotating 16x2 I2C LCD.
2. **Regional Atmospheric & Reanalysis Tier:** Open-Meteo model estimates for PM2.5 and PM10 at NMIT Yelahanka (`13.1291° N, 77.5865° E`), with an indicative CPCB AQI estimate calculated from those particulate values.
3. **Machine Learning Autoregressive Forecasting:** Multi-horizon time-series predictors (horizons $h=1$ to $6$ hours ahead) benchmarked on 60 days of continuous local hourly data (1,464 observations).
4. **Tailored Health Risk Engine:** Transparent, rule-based environmental advisory using CPCB particulate breakpoints, personalized across 7 physiological vulnerability profiles (Healthy Adult, Older Adult 65+, Child, Asthma, Chronic Bronchitis, COPD, and Cardiovascular Disease).

> **Important Engineering Labeling Standard:**
> - **MEASURED (Local IoT Sensors):** Local hardware telemetry (DHT11, MQ-135 raw ADC, MQ-7 raw ADC). MQ sensors are raw ADC responses and are NEVER misrepresented as calibrated mass concentrations or particulate matter.
> - **ESTIMATED (Open-Meteo):** Regional model-based PM2.5 and PM10 values and a derived CPCB AQI estimate.
> - **PREDICTED (ML):** Machine learning autoregressive forecasting and CPCB category classifications.
> - **AQI limitation:** The displayed CPCB value is an indicative hourly estimate from two modelled pollutants, not an official CPCB AQI reading. Official CPCB calculations use prescribed averaging periods and pollutant availability requirements.

---

## 2. End-to-End System Architecture

```mermaid
graph TD
    subgraph Edge_Hardware ["1. Edge Hardware Sensing Tier"]
        DHT11["🌡️ DHT11 (GPIO 2)<br/>Temp & Humidity"]
        MQ135["💨 MQ-135 (GPIO 32)<br/>Raw ADC Gas Response"]
        MQ7["🔥 MQ-7 (GPIO 33)<br/>Raw ADC CO Response"]
        ESP32["⚡ ESP32 DevKit V1<br/>Tensilica Dual-Core Microcontroller"]
        LCD["📟 16x2 I2C LCD (0x27)<br/>Flicker-Free Screen Rotation"]
        
        DHT11 -->|One-Wire| ESP32
        MQ135 -->|Analog ADC| ESP32
        MQ7 -->|Analog ADC| ESP32
        ESP32 -->|I2C SDA/SCL| LCD
    end

    subgraph Cloud_Telemetry ["2. Cloud Telemetry & Storage"]
        TS["☁️ ThingSpeak Cloud<br/>Channel Feeds (Fields 1-4)"]
        BL["📱 Blynk IoT Cloud<br/>Mobile App & Rate-Limited Alerts"]
        
        ESP32 -->|HTTP POST (15s)| TS
        ESP32 -->|Virtual Pins (V0-V3)| BL
    end

    subgraph Backend_Framework ["3. Python / Flask Backend Framework"]
        FL["🖥️ Flask Web Server (app.py)"]
        CONFIG["⚙️ config.py / .env<br/>Zero Leaked Secrets"]
        OM["🌐 Open-Meteo API<br/>Model Reanalysis & Forecast"]
        ML["🤖 Machine Learning Pipeline<br/>(predict.py / aqi_forecaster.joblib)"]
        RISK["⚕️ Risk Engine (risk_engine.py)<br/>7 Health Profiles & CPCB Breakpoints"]

        TS -->|REST API| FL
        OM -->|Cached REST API| FL
        CONFIG --> FL
        ML --> FL
        RISK --> FL
    end

    subgraph Client_Dashboard ["4. Client Dashboard Interface"]
        UI["🎨 Responsive Web Dashboard (HTML5 / Vanilla CSS / Chart.js)"]
        MAP["🗺️ Interactive Leaflet Map<br/>Campus Coordinates (13.1291, 77.5865)"]
        
        FL -->|JSON Endpoints & HTML| UI
        UI --> MAP
    end
```

---

## 3. Hardware Pinout & Wiring Specifications

| Component | Pin / Signal | ESP32 GPIO | Operating Voltage | Notes |
|---|---|---|---|---|
| **DHT11** | VCC | 3.3V / 5V | 3.3V / 5V | Ambient temperature & relative humidity |
| **DHT11** | DATA | GPIO 2 | 3.3V | Single-bus data line with internal pull-up |
| **DHT11** | GND | GND | 0V | Ground |
| **MQ-135** | VCC | 5V (VIN) | 5V | Air quality gas sensor heater |
| **MQ-135** | AOUT | GPIO 32 | Analog (0-3.3V) | ADC1 channel; raw ADC voltage (0-4095) |
| **MQ-135** | GND | GND | 0V | Ground |
| **MQ-7** | VCC | 5V (VIN) | 5V | Carbon monoxide gas sensor heater |
| **MQ-7** | AOUT | GPIO 33 | Analog (0-3.3V) | ADC1 channel; mapped to ThingSpeak field4 |
| **MQ-7** | GND | GND | 0V | Ground |
| **16x2 LCD** | SDA | GPIO 21 | 5V (I2C) | Default I2C SDA data line |
| **16x2 LCD** | SCL | GPIO 22 | 5V (I2C) | Default I2C SCL clock line |
| **16x2 LCD** | VCC / GND | 5V / GND | 5V | I2C PCF8574 backpack address `0x27` |

---

## 4. CPCB AQI Estimate & Machine Learning

The project calculates particulate sub-indices from hourly modelled PM2.5 and PM10 concentrations using CPCB breakpoint ranges, then uses the higher available sub-index. The current estimate is indicative only: it is not an official CPCB AQI because it does not use all required pollutants or prescribed averaging periods.

The training pipeline derives CPCB AQI values from the same local hourly particulate history and evaluates category classification and 1-6 hour forecasts using chronological splits. Run `python train_models.py` to regenerate the evaluation artifacts after collecting more local observations. These models are engineering estimates, not clinical or regulatory measurements.

---

## 5. Software Installation & Quickstart

### Prerequisites
- Python 3.10+ (tested on Python 3.14 on Windows)
- Arduino IDE 2.x for ESP32 firmware upload

### Step 1: Clone and Set Up Python Virtual Environment
In PowerShell (Windows):
```powershell
# Navigate to workspace
cd c:\Users\ankus\Downloads\Major-Project-main\Major-Project-main

# Create virtual environment
python -m venv venv

# Activate virtual environment
.\venv\Scripts\Activate.ps1

# Install dependencies
pip install -r requirements.txt
```

### Step 2: Configure Secrets
Copy the environment template:
```powershell
cp .env.example .env
```
Edit `.env` with your real keys (or use existing local credentials):
```ini
THINGSPEAK_CHANNEL_ID=3470943
THINGSPEAK_READ_API_KEY=YOUR_READ_KEY
LATITUDE=13.1291
LONGITUDE=77.5865
LOCATION_NAME=NMIT, Yelahanka, Bengaluru
```

### Step 3: Run Tests
Run the test suite:
```powershell
python -m pytest tests/ -v
```

### Step 4: Start the Flask Application
```powershell
python app.py
```
Open your web browser and navigate to:
```
http://127.0.0.1:5000/
```

---

## 6. Arduino Firmware Upload Guide

1. Open the Arduino IDE.
2. In **Boards Manager**, ensure `esp32` by Espressif Systems is installed. Select:
   - **Board:** `ESP32 Dev Module` or `Node32s`
   - **Upload Speed:** `921600` or `115200`
3. Install required libraries via **Library Manager**:
   - `Blynk` by Volodymyr Shymanskyy
   - `DHT sensor library` by Adafruit
   - `LiquidCrystal I2C` by Frank de Brabander
4. Navigate to `Air_Quality_Monitor/`:
   - Copy `secrets.example.h` to `secrets.h`.
   - Enter your Wi-Fi SSID, password, Blynk auth token, and ThingSpeak Write Key.
5. Open `Air_Quality_Monitor/Air_Quality_Monitor.ino` in Arduino IDE.
6. Connect ESP32 via Micro-USB, select the COM port, and click **Upload**.

---

## 7. REST API Endpoints Reference

| Endpoint | Method | Description |
|---|---|---|
| `/` | `GET` | Serves interactive responsive dashboard |
| `/api/current` | `GET` | Returns consolidated IoT telemetry, Open-Meteo values, and risk guidance |
| `/api/forecast` | `GET` | Returns 6-hour atmospheric baseline alongside ML autoregressive forecast |
| `/api/history?limit=50` | `GET` | Returns ThingSpeak sensor telemetry history (fields 1-4) |
| `/api/health-risk` | `POST` | Computes tailored guidance for selected health profile & activity level |
| `/api/models` | `GET` | Returns real empirical ML evaluation metrics and benchmarks |
| `/api/status` | `GET` | Diagnostics: ThingSpeak status, API cache, loaded models |

---

## 8. Educational & Clinical Disclaimer

> ⚠️ **EDUCATIONAL MONITORING PROTOTYPE DISCLAIMER:**  
> This software framework and IoT sensor node are designed strictly for educational, academic, and environmental engineering research. They do **NOT** constitute a certified medical device and do **NOT** provide clinical diagnoses, personalized medical predictions, or therapeutic prescriptions. Individuals managing respiratory or cardiovascular conditions must follow their licensed physician's clinical care plan.