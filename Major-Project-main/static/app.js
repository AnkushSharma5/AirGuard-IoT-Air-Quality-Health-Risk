/**
 * AirGuard IoT Frontend Controller
 * Integrates real-time telemetry, Open-Meteo atmospheric forecasts,
 * Chart.js visualizations, and interactive health risk advisories.
 */

document.addEventListener("DOMContentLoaded", () => {
    // Coordinate & Map Setup
    const LATITUDE = 13.1291;
    const LONGITUDE = 77.5865;
    
    let mapInstance = null;
    let forecastChartInstance = null;
    let historyChartInstance = null;

    // Initialize Map
    initMap(LATITUDE, LONGITUDE);

    // Initial Data Loads
    loadCurrentTelemetry();
    loadForecastData();
    loadSensorHistory(50);
    loadMLBenchmarks();

    // Event Listeners
    document.getElementById("refreshBtn")?.addEventListener("click", () => {
        loadCurrentTelemetry();
        loadForecastData();
        loadSensorHistory(getSelectedHistoryLimit());
    });

    document.getElementById("historyLimitSelect")?.addEventListener("change", (e) => {
        loadSensorHistory(parseInt(e.target.value, 10));
    });

    // Profile Form Listener
    const profileForm = document.getElementById("healthProfileForm");
    if (profileForm) {
        profileForm.addEventListener("submit", handleProfileSubmit);
    }

    const profileSelect = document.getElementById("profileSelect");
    if (profileSelect) {
        profileSelect.addEventListener("change", updateProfileDescription);
    }

    // Auto-refresh interval (every 60 seconds)
    setInterval(() => {
        loadCurrentTelemetry();
    }, 60000);
});

/* ==========================================================================
   Leaflet Map Initialization
   ========================================================================== */
function initMap(lat, lng) {
    const mapEl = document.getElementById("sensorMap");
    if (!mapEl) return;

    mapInstance = L.map("sensorMap", {
        center: [lat, lng],
        zoom: 15,
        zoomControl: true,
        scrollWheelZoom: false
    });

    L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
        attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
    }).addTo(mapInstance);

    const customIcon = L.divIcon({
        className: "custom-map-marker",
        html: '<div style="background-color: #10b981; width: 16px; height: 16px; border-radius: 50%; border: 3px solid white; box-shadow: 0 0 10px #10b981;"></div>',
        iconSize: [20, 20],
        iconAnchor: [10, 10]
    });

    L.marker([lat, lng], { icon: customIcon })
        .addTo(mapInstance)
        .bindPopup("<b>AirGuard Station 01</b><br>NMIT Campus, Yelahanka<br>ESP32 IoT Node")
        .openPopup();
}

/* ==========================================================================
   Telemetry & Current Overview (Section A)
   ========================================================================== */
async function loadCurrentTelemetry() {
    try {
        const response = await fetch("/api/current");
        const json = await response.json();

        if (json.status !== "ok") return;

        // Open-Meteo Current Values
        const om = json.open_meteo || {};
        const currentOm = om.current || {};

        const aqi = currentOm.cpcb_aqi;
        const pm25 = currentOm.pm2_5;
        const pm10 = currentOm.pm10;

        document.getElementById("valAqi").textContent = aqi !== null && aqi !== undefined ? aqi : "--";
        document.getElementById("valPm25").textContent = pm25 !== null && pm25 !== undefined ? pm25 : "--";
        document.getElementById("valPm10").textContent = pm10 !== null && pm10 !== undefined ? pm10 : "--";

        // AQI Category badge & color bar
        const defaultAdv = json.default_risk_advisory || {};
        const catName = defaultAdv.category || "Unknown";
        const catColor = defaultAdv.color || "#10b981";

        const badgeCat = document.getElementById("badgeAqiCategory");
        if (badgeCat) {
            badgeCat.textContent = catName;
            badgeCat.style.color = catColor;
            badgeCat.style.background = `${catColor}25`;
        }

        const barAqi = document.getElementById("barAqi");
        if (barAqi && aqi) {
            const pct = Math.min(100, Math.max(5, (aqi / 500) * 100));
            barAqi.style.width = `${pct}%`;
            barAqi.style.backgroundColor = catColor;
        }

        // Local Sensor Telemetry
        const sensor = json.sensor_telemetry || {};
        const sensorData = sensor.data || {};
        const telemetryDot = document.getElementById("telemetryStatusDot");
        const telemetryText = document.getElementById("telemetryStatusText");

        if (sensor.status === "ok") {
            telemetryDot.className = "status-indicator green";
            telemetryText.textContent = "Telemetry: Live";
        } else if (sensor.status === "sensor_warning") {
            telemetryDot.className = "status-indicator amber";
            telemetryText.textContent = "Telemetry: Warning";
        } else {
            telemetryDot.className = "status-indicator";
            telemetryText.textContent = "Telemetry: Offline";
        }

        document.getElementById("valTemp").textContent = sensorData.temperature_c !== null && sensorData.temperature_c !== undefined ? sensorData.temperature_c : "--";
        document.getElementById("valHum").textContent = sensorData.humidity_pct !== null && sensorData.humidity_pct !== undefined ? sensorData.humidity_pct : "--";
        document.getElementById("valMq135").textContent = sensorData.mq135_raw !== null && sensorData.mq135_raw !== undefined ? sensorData.mq135_raw : "--";
        document.getElementById("valMq7").textContent = sensorData.mq7_raw !== null && sensorData.mq7_raw !== undefined ? sensorData.mq7_raw : "Standby";

        if (sensorData.mq135_exceeds_threshold) {
            document.getElementById("statusMq135").textContent = "High Gas Reading";
            document.getElementById("statusMq135").style.color = "#ef4444";
        } else {
            document.getElementById("statusMq135").textContent = "Normal Response";
            document.getElementById("statusMq135").style.color = "#10b981";
        }

        if (sensor.timestamp) {
            const dt = new Date(sensor.timestamp);
            document.getElementById("sensorTimestamp").textContent = `Latest hardware transmission: ${dt.toLocaleTimeString()}`;
        }

        // Updated time
        const now = new Date();
        document.getElementById("lastUpdatedTime").textContent = `Updated: ${now.toLocaleTimeString()}`;

        // Update Live ML Category Prediction Box
        const mlCat = json.ml_category_prediction || {};
        const catBoxVal = document.getElementById("mlPredictedCategory");
        if (catBoxVal && mlCat.predicted_category) {
            catBoxVal.textContent = mlCat.predicted_category;
        }
        const catBoxSub = document.getElementById("mlClassifierMethod");
        if (catBoxSub && mlCat.method) {
            catBoxSub.textContent = mlCat.method;
        }

        // Populate initial advisory if user hasn't modified it yet
        renderAdvisoryCard(defaultAdv);

    } catch (err) {
        console.error("Error loading telemetry:", err);
    }
}

/* ==========================================================================
   6-Hour Forecast & Chart (Section B)
   ========================================================================== */
async function loadForecastData() {
    try {
        const response = await fetch("/api/forecast");
        const json = await response.json();
        if (json.status !== "ok") return;

        const omBaseline = json.baseline_forecast?.data || [];
        const mlForecast = json.ml_forecast?.forecast || [];

        // Update Live ML Multi-Horizon Boxes
        if (mlForecast.length >= 6) {
            const h1El = document.getElementById("mlPredH1");
            const h3El = document.getElementById("mlPredH3");
            const h6El = document.getElementById("mlPredH6");
            if (h1El) h1El.textContent = `${mlForecast[0].predicted_aqi} AQI`;
            if (h3El) h3El.textContent = `${mlForecast[2].predicted_aqi} AQI`;
            if (h6El) h6El.textContent = `${mlForecast[5].predicted_aqi} AQI`;
        }

        // Prepare labels and datasets (6 hours)
        const labels = [];
        const baselineAqiData = [];
        const mlAqiData = [];

        omBaseline.slice(0, 6).forEach((item, idx) => {
            const timeStr = item.time ? new Date(item.time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : `+${idx+1}h`;
            labels.push(timeStr);
            baselineAqiData.push(item.cpcb_aqi);

            // Match with ML forecast
            const mlMatch = mlForecast[idx];
            mlAqiData.push(mlMatch ? mlMatch.predicted_aqi : item.cpcb_aqi);
        });

        renderForecastChart(labels, baselineAqiData, mlAqiData);
        renderForecastCards(omBaseline.slice(0, 6));

    } catch (err) {
        console.error("Error loading forecast data:", err);
    }
}

function renderForecastChart(labels, baselineData, mlData) {
    const canvas = document.getElementById("forecastChart");
    if (!canvas) return;

    if (forecastChartInstance) {
        forecastChartInstance.destroy();
    }

    forecastChartInstance = new Chart(canvas, {
        type: "line",
        data: {
            labels: labels,
            datasets: [
                {
                    label: "Open-Meteo Baseline AQI",
                    data: baselineData,
                    borderColor: "#06b6d4",
                    backgroundColor: "rgba(6, 182, 212, 0.1)",
                    borderWidth: 2.5,
                    tension: 0.35,
                    fill: true,
                    pointBackgroundColor: "#06b6d4",
                    pointRadius: 4,
                },
                {
                    label: "ML Multi-Horizon Prediction",
                    data: mlData,
                    borderColor: "#8b5cf6",
                    borderDash: [5, 5],
                    borderWidth: 2,
                    tension: 0.3,
                    fill: false,
                    pointBackgroundColor: "#8b5cf6",
                    pointRadius: 4,
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: "#111827",
                    titleColor: "#f8fafc",
                    bodyColor: "#94a3b8",
                    borderColor: "rgba(255,255,255,0.1)",
                    borderWidth: 1,
                    padding: 10,
                }
            },
            scales: {
                x: {
                    grid: { color: "rgba(255, 255, 255, 0.05)" },
                    ticks: { color: "#94a3b8", font: { family: 'Inter', size: 12 } }
                },
                y: {
                    grid: { color: "rgba(255, 255, 255, 0.05)" },
                    ticks: { color: "#94a3b8", font: { family: 'Inter', size: 12 } },
                    suggestedMin: 30,
                }
            }
        }
    });
}

function renderForecastCards(items) {
    const container = document.getElementById("forecastCardsRow");
    if (!container) return;

    container.innerHTML = "";

    items.forEach((item, idx) => {
        const timeObj = item.time ? new Date(item.time) : null;
        const timeStr = timeObj ? timeObj.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : `+${idx+1}h`;
        const aqi = item.cpcb_aqi ?? "--";
        const category = getCpcbCategory(aqi);
        const catName = category.name;
        const catColor = category.color;

        const card = document.createElement("div");
        card.className = "forecast-mini-card";
        card.innerHTML = `
            <div class="forecast-time">${timeStr}</div>
            <div class="forecast-aqi">${aqi}</div>
            <div class="forecast-cat" style="color: ${catColor}; background: ${catColor}20;">${catName}</div>
            <div style="font-size: 11px; color: #64748b; margin-top: 6px;">PM2.5: ${item.pm2_5 || '--'}</div>
        `;
        container.appendChild(card);
    });
}

function getCpcbCategory(aqi) {
    if (aqi === "--" || aqi === null || aqi === undefined) {
        return { name: "Unavailable", color: "#6b7280" };
    }
    if (aqi <= 50) return { name: "Good", color: "#10b981" };
    if (aqi <= 100) return { name: "Satisfactory", color: "#f59e0b" };
    if (aqi <= 200) return { name: "Moderate", color: "#f97316" };
    if (aqi <= 300) return { name: "Poor", color: "#ef4444" };
    if (aqi <= 400) return { name: "Very Poor", color: "#8b5cf6" };
    return { name: "Severe", color: "#881337" };
}

/* ==========================================================================
   Sensor History & Chart (Section C)
   ========================================================================== */
function getSelectedHistoryLimit() {
    const sel = document.getElementById("historyLimitSelect");
    return sel ? parseInt(sel.value, 10) : 50;
}

async function loadSensorHistory(limit) {
    try {
        const response = await fetch(`/api/history?limit=${limit}`);
        const json = await response.json();
        if (json.status !== "ok") return;

        const feeds = json.feeds || [];
        const labels = [];
        const tempData = [];
        const humData = [];
        const mq135Data = [];

        feeds.forEach(f => {
            const dt = f.timestamp ? new Date(f.timestamp) : null;
            labels.push(dt ? dt.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' }) : "");
            tempData.push(f.temperature);
            humData.push(f.humidity);
            mq135Data.push(f.mq135_raw);
        });

        renderHistoryChart(labels, tempData, humData, mq135Data);

    } catch (err) {
        console.error("Error loading sensor history:", err);
    }
}

function renderHistoryChart(labels, temps, hums, gases) {
    const canvas = document.getElementById("historyChart");
    if (!canvas) return;

    if (historyChartInstance) {
        historyChartInstance.destroy();
    }

    historyChartInstance = new Chart(canvas, {
        type: "line",
        data: {
            labels: labels,
            datasets: [
                {
                    label: "Temperature (°C)",
                    data: temps,
                    borderColor: "#f59e0b",
                    borderWidth: 2,
                    tension: 0.3,
                    yAxisID: "yTemp",
                    pointRadius: 2,
                },
                {
                    label: "Humidity (%)",
                    data: hums,
                    borderColor: "#38bdf8",
                    borderWidth: 2,
                    tension: 0.3,
                    yAxisID: "yTemp",
                    pointRadius: 2,
                },
                {
                    label: "MQ-135 Gas Response (ADC)",
                    data: gases,
                    borderColor: "#10b981",
                    borderWidth: 2,
                    tension: 0.3,
                    yAxisID: "yGas",
                    pointRadius: 2,
                }
            ]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: "top",
                    labels: { color: "#94a3b8", font: { family: 'Inter', size: 12 } }
                },
                tooltip: {
                    backgroundColor: "#111827",
                    titleColor: "#f8fafc",
                    bodyColor: "#94a3b8",
                    borderColor: "rgba(255,255,255,0.1)",
                    borderWidth: 1,
                }
            },
            scales: {
                x: {
                    grid: { color: "rgba(255, 255, 255, 0.05)" },
                    ticks: { color: "#94a3b8", font: { family: 'Inter', size: 11 } }
                },
                yTemp: {
                    type: "linear",
                    position: "left",
                    grid: { color: "rgba(255, 255, 255, 0.05)" },
                    ticks: { color: "#94a3b8", font: { family: 'Inter', size: 11 } },
                    title: { display: true, text: "Temp / Hum", color: "#64748b" }
                },
                yGas: {
                    type: "linear",
                    position: "right",
                    grid: { drawOnChartArea: false },
                    ticks: { color: "#10b981", font: { family: 'Inter', size: 11 } },
                    title: { display: true, text: "MQ-135 (ADC)", color: "#10b981" }
                }
            }
        }
    });
}

/* ==========================================================================
   ML Benchmarks Loader (Section D)
   ========================================================================== */
async function loadMLBenchmarks() {
    try {
        const response = await fetch("/api/models");
        const json = await response.json();
        if (json.status !== "ok") return;

        // Multi-Horizon Forecasting Benchmark Table
        const fctData = json.forecasting_evaluation?.results_by_horizon || {};
        const fctTbody = document.querySelector("#forecastBenchmarkTable tbody");
        if (fctTbody) {
            fctTbody.innerHTML = "";
            // Display horizons h=1, h=3, h=6
            ["horizon_1h", "horizon_3h", "horizon_6h"].forEach(hKey => {
                const list = fctData[hKey] || [];
                list.forEach(item => {
                    const tr = document.createElement("tr");
                    if (item.model.includes("Linear Regression") || (hKey === "horizon_1h" && item.model.includes("Linear Regression"))) {
                        tr.className = "highlight-row";
                    }
                    tr.innerHTML = `
                        <td>+${item.horizon_hours} hour</td>
                        <td>${item.model}</td>
                        <td>${item.MAE}</td>
                        <td>${item.RMSE}</td>
                        <td>${item.R2}</td>
                    `;
                    fctTbody.appendChild(tr);
                });
            });
        }

        // Classification Benchmark Table
        const clsData = json.classification_evaluation?.results || [];
        const clsTbody = document.querySelector("#classificationBenchmarkTable tbody");
        if (clsTbody) {
            clsTbody.innerHTML = "";
            clsData.forEach(item => {
                const tr = document.createElement("tr");
                if (item.model.includes("Gradient Boosting")) {
                    tr.className = "highlight-row";
                }
                tr.innerHTML = `
                    <td>${item.model}</td>
                    <td>${(item.accuracy * 100).toFixed(1)}%</td>
                    <td>${(item.precision_macro * 100).toFixed(1)}%</td>
                    <td>${(item.recall_macro * 100).toFixed(1)}%</td>
                    <td>${item.macro_f1.toFixed(3)}</td>
                `;
                clsTbody.appendChild(tr);
            });
        }

    } catch (err) {
        console.error("Error loading ML benchmarks:", err);
    }
}

/* ==========================================================================
   Personalized Health Assessment Form & Risk Factor Renderer
   ========================================================================== */
const CONDITION_EXPLANATIONS = {
    none: "No diagnosed chronic respiratory or cardiovascular illness (standard physiological baseline).",
    asthma: "Hyperreactive airways prone to bronchospasms, wheezing, and irritation from fine particulates (PM2.5).",
    bronchitis: "Persistent bronchial inflammation, excess mucus hypersecretion, and frequent coughing.",
    copd: "Permanent airflow limitation; inhaled environmental pollutants trigger severe acute exacerbations.",
    cardiovascular: "Coronary artery or hypertensive disease sensitive to vascular vasoconstriction from particle pollution."
};

function updateConditionDescription(e) {
    const val = e.target.value;
    const explainerEl = document.getElementById("conditionExplainer");
    if (explainerEl && CONDITION_EXPLANATIONS[val]) {
        explainerEl.textContent = CONDITION_EXPLANATIONS[val];
    }
}

// Add event listener for condition select
document.getElementById("respiratoryConditionSelect")?.addEventListener("change", updateConditionDescription);

async function handleProfileSubmit(e) {
    e.preventDefault();

    const ageGroup = document.getElementById("ageGroupSelect")?.value || "adult";
    const respCondition = document.getElementById("respiratoryConditionSelect")?.value || "none";
    const activityRadios = document.getElementsByName("activity_level");
    let activityLevel = "moderate";
    for (const r of activityRadios) {
        if (r.checked) {
            activityLevel = r.value;
            break;
        }
    }

    const symptoms = [];
    if (document.getElementById("sympWheeze")?.checked) symptoms.push("wheezing");
    if (document.getElementById("sympDyspnea")?.checked) symptoms.push("shortness_of_breath");
    if (document.getElementById("sympCough")?.checked) symptoms.push("cough");

    try {
        const response = await fetch("/api/health-risk", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({
                age_group: ageGroup,
                respiratory_condition: respCondition,
                activity_level: activityLevel,
                has_respiratory_problem: (respCondition !== "none"),
                symptoms: symptoms
            })
        });

        const advisory = await response.json();
        renderAdvisoryCard(advisory);

        // Smooth scroll to Risk Factor Results section
        document.getElementById("risk-factor-results")?.scrollIntoView({ behavior: "smooth" });

    } catch (err) {
        console.error("Error submitting profile assessment:", err);
    }
}

function renderAdvisoryCard(adv) {
    if (!adv) return;

    const banner = document.getElementById("advisoryBanner");
    const riskBadge = document.getElementById("advisoryRiskLevel");
    const catTitle = document.getElementById("advisoryCategoryTitle");
    const catDesc = document.getElementById("advisoryCategoryDesc");
    const outdoorEl = document.getElementById("advisoryOutdoor");
    const maskEl = document.getElementById("advisoryMask");
    const profileNameEl = document.getElementById("advisoryProfileName");
    const listEl = document.getElementById("advisoryPrecautionsList");

    const riskScoreEl = document.getElementById("riskFactorScore");
    const riskMultEl = document.getElementById("riskFactorMultiplier");
    const factorExplText = document.getElementById("factorExplanationText");

    const color = adv.color || "#10b981";

    if (banner) {
        banner.style.background = `linear-gradient(135deg, ${color}25 0%, rgba(17, 24, 39, 0.95) 100%)`;
        banner.style.borderBottom = `1px solid ${color}40`;
    }

    if (riskBadge) {
        riskBadge.textContent = `${adv.risk_level || 'Moderate'} Risk`;
        riskBadge.style.background = `${color}30`;
        riskBadge.style.color = color;
    }

    if (catTitle) {
        const aqiText = adv.aqi_value !== null && adv.aqi_value !== undefined ? ` (CPCB AQI estimate: ${adv.aqi_value})` : '';
        catTitle.textContent = `Category: ${adv.category || 'Good'}${aqiText}`;
    }

    if (catDesc) {
        catDesc.textContent = adv.category_description || "Ambient atmospheric assessment.";
    }

    if (riskScoreEl) {
        riskScoreEl.textContent = adv.risk_factor_score !== undefined ? `${adv.risk_factor_score}` : '--';
        riskScoreEl.style.color = color;
    }

    if (riskMultEl) {
        const mult = adv.risk_factor_multiplier ? `${adv.risk_factor_multiplier}x` : '1.0x';
        riskMultEl.textContent = `Vulnerability Factor: ${mult} • Scale 0-100`;
    }

    if (factorExplText && adv.risk_factor_explanation) {
        factorExplText.textContent = adv.risk_factor_explanation;
    }

    if (outdoorEl) {
        outdoorEl.textContent = adv.outdoor_recommendation || "Safe for outdoor activities.";
    }

    if (maskEl) {
        maskEl.textContent = adv.mask_recommendation || "Not required.";
    }

    if (profileNameEl && adv.profile) {
        profileNameEl.textContent = adv.profile.name || "Healthy Adult";
    }

    if (listEl && adv.tailored_precautions) {
        listEl.innerHTML = "";
        adv.tailored_precautions.forEach(item => {
            const li = document.createElement("li");
            li.textContent = item;
            li.style.borderLeftColor = color;
            listEl.appendChild(li);
        });
    }
}
