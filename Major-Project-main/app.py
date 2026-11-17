"""
Flask Application for the Air Quality Monitoring & Health Risk Advisory System.

Integrates:
- Real-time IoT sensor telemetry from ThingSpeak (MEASURED)
- Ambient particulate & AQI model estimates from Open-Meteo (ESTIMATED)
- Multi-horizon ML forecasting & category prediction (PREDICTED)
- Rule-based profile-tailored health risk advisory (risk_engine.py)

Strict Design Standards:
- Zero secrets hard-coded (all imported from config.py / .env)
- Explicit data categorization: MEASURED vs ESTIMATED vs PREDICTED
- No misleading medical claims or diagnoses
"""

import json
from pathlib import Path
from flask import Flask, render_template, jsonify, request
import config
import air_quality_api
import sensor_data
import risk_engine
import predict

app = Flask(__name__)
MODELS_DIR = Path("models")


@app.route("/")
def index():
    """Render the main responsive dashboard."""
    return render_template(
        "index.html",
        location_name=config.LOCATION_NAME,
        latitude=config.LATITUDE,
        longitude=config.LONGITUDE,
        profiles=risk_engine.list_profiles(),
    )


@app.route("/favicon.ico")
def favicon():
    """Favicon endpoint returning No Content to prevent 404."""
    return ("", 204)


@app.route("/api/current")
def api_current():
    """Return consolidated current readings from sensors, Open-Meteo, and initial risk advisory."""
    # 1. Fetch live local sensor telemetry
    sensor_res = sensor_data.get_latest_sensor_reading()

    # 2. Fetch Open-Meteo model estimates
    om_res = air_quality_api.get_air_quality()

    # 3. Derive risk advisory using the estimated CPCB AQI (or None if unavailable)
    current_om = om_res.get("current") or {}
    aqi_val = current_om.get("cpcb_aqi")
    pm2_5_val = current_om.get("pm2_5")
    pm10_val = current_om.get("pm10")

    risk_advisory = risk_engine.evaluate_risk(
        aqi=aqi_val,
        pm2_5=pm2_5_val,
        pm10=pm10_val,
        profile_id="healthy_adult",
        activity_level="moderate",
    )

    # 4. ML Category prediction
    ml_category = predict.predict_category(
        pm2_5=pm2_5_val,
        pm10=pm10_val,
    )

    return jsonify({
        "status": "ok",
        "location": {
            "name": config.LOCATION_NAME,
            "latitude": config.LATITUDE,
            "longitude": config.LONGITUDE,
        },
        "sensor_telemetry": sensor_res,
        "open_meteo": om_res,
        "ml_category_prediction": ml_category,
        "default_risk_advisory": risk_advisory,
    })


@app.route("/api/forecast")
def api_forecast():
    """Return Open-Meteo 6-hour forecast alongside ML multi-horizon forecast overlay."""
    om_res = air_quality_api.get_air_quality()
    om_forecast = om_res.get("forecast") or []

    # Prepare past AQI sequence for ML forecaster
    current_om = om_res.get("current") or {}
    current_aqi = current_om.get("cpcb_aqi", 60)
    aqi_history = [current_aqi] * 5  # Seed with current observation

    ml_forecast = predict.predict_multi_horizon_aqi(
        recent_aqi_values=aqi_history,
    )

    return jsonify({
        "status": "ok",
        "baseline_forecast": {
            "source": "Open-Meteo Model Estimate (Baseline)",
            "data": om_forecast,
        },
        "ml_forecast": ml_forecast,
    })


@app.route("/api/history")
def api_history():
    """Return historical ThingSpeak sensor readings with limit filter."""
    limit = request.args.get("limit", default=50, type=int)
    history_res = sensor_data.get_sensor_history(results=limit)
    return jsonify(history_res)


@app.route("/api/health-risk", methods=["POST"])
def api_health_risk():
    """Generate tailored health advisory recommendations based on user profile.

    Does NOT store any PII. Changes guidance only, never sensor values.
    """
    payload = request.get_json(silent=True) or {}
    profile_id = payload.get("profile_id", "healthy_adult")
    activity_level = payload.get("activity_level", "moderate")

    # Get latest AQI from Open-Meteo
    om_res = air_quality_api.get_air_quality()
    current_om = om_res.get("current") or {}
    aqi_val = current_om.get("cpcb_aqi")
    pm2_5_val = current_om.get("pm2_5")
    pm10_val = current_om.get("pm10")

    advisory = risk_engine.evaluate_risk(
        aqi=aqi_val,
        pm2_5=pm2_5_val,
        pm10=pm10_val,
        profile_id=profile_id,
        activity_level=activity_level,
        respiratory_condition=payload.get("respiratory_condition"),
        age_group=payload.get("age_group"),
        has_respiratory_problem=payload.get("has_respiratory_problem"),
    )

    return jsonify(advisory)


@app.route("/api/models")
def api_models():
    """Return real saved ML evaluation metrics for dashboard display."""
    eval_json_path = MODELS_DIR / "evaluation_results.json"
    cls_json_path = MODELS_DIR / "classification_metrics.json"

    eval_data = {}
    cls_data = {}

    if eval_json_path.exists():
        try:
            with open(eval_json_path, "r", encoding="utf-8") as f:
                eval_data = json.load(f)
        except Exception as e:
            eval_data = {"error": f"Failed reading evaluation results: {str(e)}"}

    if cls_json_path.exists():
        try:
            with open(cls_json_path, "r", encoding="utf-8") as f:
                cls_data = json.load(f)
        except Exception as e:
            cls_data = {"error": f"Failed reading classification metrics: {str(e)}"}

    return jsonify({
        "status": "ok",
        "forecasting_evaluation": eval_data,
        "classification_evaluation": cls_data,
    })


@app.route("/api/status")
def api_status():
    """System diagnostic and status endpoint."""
    return jsonify({
        "system": "IoT Air Quality & Risk Advisory System",
        "version": "2.0.0",
        "location": config.LOCATION_NAME,
        "open_meteo_cache": air_quality_api.get_cache_info(),
        "thingspeak_configured": bool(config.THINGSPEAK_CHANNEL_ID and config.THINGSPEAK_READ_API_KEY),
        "models_available": {
            "classifier": (MODELS_DIR / "aqi_classifier.joblib").exists(),
            "forecaster": (MODELS_DIR / "aqi_forecaster.joblib").exists(),
        },
    })


if __name__ == "__main__":
    app.run(
        host=config.FLASK_HOST,
        port=config.FLASK_PORT,
        debug=config.FLASK_DEBUG,
    )