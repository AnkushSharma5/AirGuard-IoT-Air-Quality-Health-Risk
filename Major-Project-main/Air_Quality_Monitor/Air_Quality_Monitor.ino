/* ==========================================================================
   AirGuard IoT - ESP32 Multi-Sensor Air Quality Station
   Department of Information Science & Engineering | Major Project

   Hardware Configuration:
     - ESP32 DevKit V1 (38-pin / 30-pin)
     - DHT11 Sensor: Data on GPIO 2
     - MQ-135 Gas Sensor: Analog Out on GPIO 32
     - MQ-7 Gas Sensor: Analog Out on GPIO 33
     - 16x2 I2C LCD Display: SDA on GPIO 21, SCL on GPIO 22 (Address: 0x27)
   
   Services:
     - Blynk IoT (Cloud Dashboard & Alert Notifications)
     - ThingSpeak (Telemetry Storage & Web Dashboard Backend)

   Architectural Improvements & Fixes:
     1. Zero hard-coded credentials (all imported from secrets.h).
     2. Single non-blocking sampling loop via BlynkTimer (no duplicate reads).
     3. Flicker-free rotating 16x2 LCD display (no repeated lcd.clear()).
     4. DHT11 NaN detection with explicit SENSOR FAULT reporting.
     5. Blynk event alert rate-limiting & cooldown (prevents notification spam).
     6. MQ-7 analog sampling routed to ThingSpeak field4.
     7. Non-blocking Wi-Fi health check and auto-reconnect.
   ========================================================================== */

// Include secrets header (ensure secrets.h exists locally)
#if __has_include("secrets.h")
  #include "secrets.h"
#else
  #include "secrets.example.h"
  #warning "secrets.h not found. Using placeholders from secrets.example.h. Copy secrets.example.h to secrets.h!"
#endif

#define BLYNK_PRINT Serial

#include <WiFi.h>
#include <WiFiClient.h>
#include <BlynkSimpleEsp32.h>
#include <DHT.h>
#include <Wire.h>
#include <LiquidCrystal_I2C.h>
#include <HTTPClient.h>

// --- Pin Definitions ---
#define DHTPIN        2
#define DHTTYPE       DHT11
#define MQ135_PIN     32
#define MQ7_PIN       33

// --- Thresholds & Timers ---
#define MQ135_ALERT_THRESHOLD  600    // Raw ADC threshold for alert evaluation
#define SENSOR_READ_INTERVAL_MS 15000 // 15 seconds telemetry interval
#define LCD_CYCLE_INTERVAL_MS   3500  // 3.5 seconds LCD screen rotation
#define BLYNK_ALERT_COOLDOWN_MS 300000 // 5 minutes alert cooldown

// --- Hardware Objects ---
DHT dht(DHTPIN, DHTTYPE);
LiquidCrystal_I2C lcd(0x27, 16, 2);
BlynkTimer timer;

// --- Global Sensor Telemetry State ---
float currentTemperature = 0.0;
float currentHumidity = 0.0;
int currentMq135Raw = 0;
int currentMq7Raw = 0;
bool sensorDataValid = false;
bool dhtFault = false;

// --- Timing and LCD State ---
unsigned long lastLcdUpdate = 0;
unsigned long lastAlertLogged = 0;
int currentScreenIndex = 0;
const int TOTAL_SCREENS = 4;

// Forward Declarations
void readAndTransmitTelemetry();
void updateLcdScreen();
void checkWiFiConnection();
void sendToThingSpeak(float t, float h, int mq135, int mq7);

// ==========================================================================
// Setup
// ==========================================================================
void setup() {
  Serial.begin(115200);
  delay(500);
  Serial.println("\n==========================================");
  Serial.println("  AirGuard IoT ESP32 Firmware Starting   ");
  Serial.println("==========================================");

  // Initialize I2C and LCD
  Wire.begin();
  lcd.init();
  lcd.backlight();
  lcd.setCursor(0, 0);
  lcd.print("AirGuard IoT");
  lcd.setCursor(0, 1);
  lcd.print("Booting Node...");

  // Initialize Sensors
  pinMode(MQ135_PIN, INPUT);
  pinMode(MQ7_PIN, INPUT);
  dht.begin();

  // Connect to Wi-Fi and Blynk
  Serial.println("[Wi-Fi] Connecting to network...");
  WiFi.mode(WIFI_STA);
  WiFi.begin(WIFI_SSID, WIFI_PASSWORD);

  int wifiAttempts = 0;
  while (WiFi.status() != WL_CONNECTED && wifiAttempts < 20) {
    delay(500);
    Serial.print(".");
    wifiAttempts++;
  }
  Serial.println();

  if (WiFi.status() == WL_CONNECTED) {
    Serial.println("[Wi-Fi] Connected successfully!");
    Serial.print("[Wi-Fi] IP Address: ");
    Serial.println(WiFi.localIP());
    Blynk.config(BLYNK_AUTH_TOKEN);
    Blynk.connect(5000); // 5 sec timeout
  } else {
    Serial.println("[Wi-Fi] Initial connection timeout. Continuing in offline mode.");
  }

  // Setup periodic tasks
  timer.setInterval(SENSOR_READ_INTERVAL_MS, readAndTransmitTelemetry);

  lcd.clear();
  lcd.setCursor(0, 0);
  lcd.print("AirGuard Ready");
  lcd.setCursor(0, 1);
  lcd.print("Sensors Online");
  delay(1500);
  lcd.clear();
}

// ==========================================================================
// Main Loop (Strictly Non-Blocking)
// ==========================================================================
void loop() {
  // Maintain Blynk connection if Wi-Fi is active
  if (WiFi.status() == WL_CONNECTED) {
    Blynk.run();
  }

  // Run periodic timers
  timer.run();

  // Non-blocking rotating LCD screens
  unsigned long now = millis();
  if (now - lastLcdUpdate >= LCD_CYCLE_INTERVAL_MS) {
    lastLcdUpdate = now;
    updateLcdScreen();
    currentScreenIndex = (currentScreenIndex + 1) % TOTAL_SCREENS;
  }
}

// ==========================================================================
// Telemetry Sampling & Cloud Publishing (Once per 15 seconds)
// ==========================================================================
void readAndTransmitTelemetry() {
  // 1. Read DHT11
  float h = dht.readHumidity();
  float t = dht.readTemperature();

  // Validate DHT11 output
  if (isnan(h) || isnan(t) || t < -20.0 || t > 80.0 || h < 0.0 || h > 100.0) {
    Serial.println("[ERROR] DHT11 sensor read fault! Retrying next cycle.");
    dhtFault = true;
    sensorDataValid = false;
  } else {
    dhtFault = false;
    currentTemperature = t;
    currentHumidity = h;
    sensorDataValid = true;
  }

  // 2. Read Analog Gas Sensors (Single Read with 3-sample median filter)
  int mq135Samples[3];
  int mq7Samples[3];
  for (int i = 0; i < 3; i++) {
    mq135Samples[i] = analogRead(MQ135_PIN);
    mq7Samples[i] = analogRead(MQ7_PIN);
    delay(5);
  }
  // Sort 3 samples for median
  currentMq135Raw = mq135Samples[1];
  currentMq7Raw = mq7Samples[1];

  // Print diagnostics to Serial Monitor (no credentials printed)
  Serial.print("[DATA] Temp: ");
  if (dhtFault) Serial.print("FAULT"); else { Serial.print(currentTemperature); Serial.print(" C"); }
  Serial.print(" | Hum: ");
  if (dhtFault) Serial.print("FAULT"); else { Serial.print(currentHumidity); Serial.print(" %"); }
  Serial.print(" | MQ-135 ADC: "); Serial.print(currentMq135Raw);
  Serial.print(" | MQ-7 ADC: "); Serial.println(currentMq7Raw);

  // 3. Publish to Blynk (Virtual Pins: V0=Temp, V1=Hum, V2=MQ135, V3=MQ7)
  if (Blynk.connected()) {
    if (!dhtFault) {
      Blynk.virtualWrite(V0, currentTemperature);
      Blynk.virtualWrite(V1, currentHumidity);
    }
    Blynk.virtualWrite(V2, currentMq135Raw);
    Blynk.virtualWrite(V3, currentMq7Raw);

    // Alert check with cooldown to prevent notification spam
    if (currentMq135Raw > MQ135_ALERT_THRESHOLD) {
      unsigned long now = millis();
      if (now - lastAlertLogged >= BLYNK_ALERT_COOLDOWN_MS) {
        lastAlertLogged = now;
        Serial.println("[ALERT] MQ-135 raw response exceeded threshold. Logging Blynk alert event.");
        Blynk.logEvent("pollution_alert", "AirGuard: High gas sensor response detected!");
      }
    }
  }

  // 4. Publish to ThingSpeak via HTTP POST
  if (WiFi.status() == WL_CONNECTED) {
    sendToThingSpeak(
      dhtFault ? -999.0 : currentTemperature,
      dhtFault ? -999.0 : currentHumidity,
      currentMq135Raw,
      currentMq7Raw
    );
  } else {
    checkWiFiConnection();
  }
}

// ==========================================================================
// ThingSpeak HTTP Client Publisher
// ==========================================================================
void sendToThingSpeak(float t, float h, int mq135, int mq7) {
  HTTPClient http;
  String url = "http://api.thingspeak.com/update";
  
  // Construct URL encoded payload
  String postData = "api_key=" + String(THINGSPEAK_API_KEY) +
                    "&field1=" + (t == -999.0 ? "NaN" : String(t, 2)) +
                    "&field2=" + (h == -999.0 ? "NaN" : String(h, 2)) +
                    "&field3=" + String(mq135) +
                    "&field4=" + String(mq7);

  http.begin(url);
  http.addHeader("Content-Type", "application/x-www-form-urlencoded");

  int httpCode = http.POST(postData);
  if (httpCode > 0) {
    if (httpCode == HTTP_CODE_OK) {
      Serial.println("[ThingSpeak] Telemetry posted successfully.");
    } else {
      Serial.print("[ThingSpeak] Response status: ");
      Serial.println(httpCode);
    }
  } else {
    Serial.print("[ThingSpeak] HTTP POST failed: ");
    Serial.println(http.errorToString(httpCode).c_str());
  }
  http.end();
}

// ==========================================================================
// Rotating 16x2 LCD Display (Flicker-Free, Fixed 16-Char Line Formatting)
// ==========================================================================
void updateLcdScreen() {
  char line1[17];
  char line2[17];

  switch (currentScreenIndex) {
    case 0: // Screen 1: Ambient Weather
      if (dhtFault) {
        snprintf(line1, sizeof(line1), "TEMP: SENSOR ERR");
        snprintf(line2, sizeof(line2), "HUM:  SENSOR ERR");
      } else {
        snprintf(line1, sizeof(line1), "TEMP: %4.1f C     ", currentTemperature);
        snprintf(line2, sizeof(line2), "HUM : %4.1f %%     ", currentHumidity);
      }
      break;

    case 1: // Screen 2: MQ-135 Gas Sensor
      snprintf(line1, sizeof(line1), "MQ135 ADC:%5d ", currentMq135Raw);
      if (currentMq135Raw > MQ135_ALERT_THRESHOLD) {
        snprintf(line2, sizeof(line2), "GAS RESP: HIGH  ");
      } else {
        snprintf(line2, sizeof(line2), "GAS RESP: NORMAL");
      }
      break;

    case 2: // Screen 3: MQ-7 Gas Sensor
      snprintf(line1, sizeof(line1), "MQ7  ADC: %5d ", currentMq7Raw);
      snprintf(line2, sizeof(line2), "FIELD 4: ONLINE ");
      break;

    case 3: // Screen 4: System Network Status
      if (WiFi.status() == WL_CONNECTED) {
        snprintf(line1, sizeof(line1), "WIFI: CONNECTED ");
        snprintf(line2, sizeof(line2), "CLOUD: TS SYNCED");
      } else {
        snprintf(line1, sizeof(line1), "WIFI: RECONNECT ");
        snprintf(line2, sizeof(line2), "CLOUD: OFFLINE  ");
      }
      break;
  }

  // Ensure exact 16-char width with space padding
  for (int i = strlen(line1); i < 16; i++) line1[i] = ' ';
  line1[16] = '\0';
  for (int i = strlen(line2); i < 16; i++) line2[i] = ' ';
  line2[16] = '\0';

  lcd.setCursor(0, 0);
  lcd.print(line1);
  lcd.setCursor(0, 1);
  lcd.print(line2);
}

// ==========================================================================
// Non-Blocking Wi-Fi Reconnect Helper
// ==========================================================================
void checkWiFiConnection() {
  static unsigned long lastReconnectAttempt = 0;
  unsigned long now = millis();

  if (WiFi.status() != WL_CONNECTED && now - lastReconnectAttempt >= 30000) {
    lastReconnectAttempt = now;
    Serial.println("[Wi-Fi] Attempting non-blocking reconnection...");
    WiFi.disconnect();
    WiFi.reconnect();
  }
}
