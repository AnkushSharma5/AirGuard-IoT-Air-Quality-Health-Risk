"""
Model Inference and Prediction Module.

Provides clean interfaces to load trained models and generate predictions:
- Air Quality Category Classification (Task 1)
- 1-6 Hour Multi-Horizon AQI Forecasting (Task 2)

Design Rules:
1. Strictly labels predictions as "PREDICTED (ML)".
2. Robust fallbacks: if models are missing or features are incomplete,
   gracefully falls back to rule-based classification and persistence forecasting.
3. Never fabricates values or claims medical diagnostics.
"""

from pathlib import Path
from typing import Dict, Any, List, Optional
import numpy as np
import pandas as pd
import joblib
from risk_engine import calculate_cpcb_aqi, get_aqi_category

MODELS_DIR = Path("models")
CLASSIFIER_PATH = MODELS_DIR / "aqi_classifier.joblib"
FORECASTER_PATH = MODELS_DIR / "aqi_forecaster.joblib"

_cached_classifier = None
_cached_forecaster = None


def get_classifier():
    """Load cached classification artifact."""
    global _cached_classifier
    if _cached_classifier is None and CLASSIFIER_PATH.exists():
        try:
            _cached_classifier = joblib.load(CLASSIFIER_PATH)
        except Exception as e:
            print(f"Warning: Failed to load {CLASSIFIER_PATH}: {e}")
    return _cached_classifier


def get_forecaster():
    """Load cached forecasting artifact."""
    global _cached_forecaster
    if _cached_forecaster is None and FORECASTER_PATH.exists():
        try:
            _cached_forecaster = joblib.load(FORECASTER_PATH)
        except Exception as e:
            print(f"Warning: Failed to load {FORECASTER_PATH}: {e}")
    return _cached_forecaster


def predict_category(
    pm2_5: Optional[float],
    pm10: Optional[float] = None,
    carbon_monoxide: Optional[float] = None,
    nitrogen_dioxide: Optional[float] = None,
    sulphur_dioxide: Optional[float] = None,
    ozone: Optional[float] = None,
) -> Dict[str, Any]:
    """Predict CPCB Air Quality category from ambient pollutant concentrations.

    Returns:
        Dict with predicted category, confidence/probability (if available),
        method used ("ML Model" vs "Rule-based Fallback"), and source.
    """
    if pm2_5 is None and pm10 is None:
        return {
            "status": "unavailable",
            "predicted_category": None,
            "method": "None",
            "source": "PREDICTED (ML)",
            "message": "Missing required PM2.5 pollutant concentration.",
        }

    cpcb_category = get_aqi_category(
        calculate_cpcb_aqi(pm2_5=pm2_5, pm10=pm10)
    )
    clf_bundle = get_classifier()
    known_classes = clf_bundle.get("classes", []) if clf_bundle else []
    model_covers_category = (
        pm2_5 is not None
        and cpcb_category is not None
        and cpcb_category["name"] in known_classes
    )

    if clf_bundle is not None and model_covers_category:
        try:
            feature_cols = clf_bundle["feature_cols"]
            row_data = {
                "pm2_5": pm2_5,
                "pm10": pm10 if pm10 is not None else pm2_5 * 1.5,
                "carbon_monoxide": carbon_monoxide if carbon_monoxide is not None else 300.0,
                "nitrogen_dioxide": nitrogen_dioxide if nitrogen_dioxide is not None else 20.0,
                "sulphur_dioxide": sulphur_dioxide if sulphur_dioxide is not None else 5.0,
                "ozone": ozone if ozone is not None else 40.0,
            }
            X_df = pd.DataFrame([[row_data[c] for c in feature_cols]], columns=feature_cols)
            model = clf_bundle["model"]
            prediction = model.predict(X_df)[0]

            return {
                "status": "ok",
                "predicted_category": prediction,
                "model_name": clf_bundle.get("model_name", "Classification Pipeline"),
                "method": "Trained Classifier (Gradient Boosting / Random Forest)",
                "source": "PREDICTED (ML)",
            }
        except Exception as e:
            print(f"Inference error in classifier: {e}, falling back to rule-based.")

    # Fallback to CPCB breakpoint calculation.
    aqi = calculate_cpcb_aqi(pm2_5=pm2_5, pm10=pm10)
    category = get_aqi_category(aqi)
    if category is None:
        return {
            "status": "unavailable",
            "predicted_category": None,
            "method": "None",
            "source": "PREDICTED (Rule-Based Baseline)",
            "message": "No valid particulate concentration was available.",
        }

    return {
        "status": "ok",
        "predicted_category": category["name"],
        "method": "Rule-Based Baseline (CPCB PM Breakpoints)",
        "source": "PREDICTED (Rule-Based Baseline)",
    }


def predict_multi_horizon_aqi(
    recent_aqi_values: List[float],
    current_hour: int = 12,
    day_of_week: int = 0,
) -> Dict[str, Any]:
    """Forecast CPCB AQI estimates for horizons 1 through 6 hours ahead.

    Args:
        recent_aqi_values: List of recent hourly AQI readings (at least latest 1).
        current_hour: Hour of day (0-23).
        day_of_week: Day of week (0=Mon, 6=Sun).

    Returns:
        Dict containing 1-6 hour forecast list with predicted values and methods.
    """
    if not recent_aqi_values:
        return {
            "status": "unavailable",
            "forecast": [],
            "source": "PREDICTED (ML)",
            "message": "No recent AQI history provided.",
        }

    latest_aqi = float(recent_aqi_values[-1])
    forecaster = get_forecaster()

    forecast_points = []

    if forecaster is not None:
        models_dict = forecaster.get("models", {})
        feature_cols = forecaster.get("feature_cols", [])

        # Construct input features from available lag history
        lags = {}
        for lag in [1, 2, 3, 6, 12, 24]:
            if len(recent_aqi_values) >= lag:
                lags[f"aqi_lag_{lag}"] = float(recent_aqi_values[-lag])
            else:
                lags[f"aqi_lag_{lag}"] = latest_aqi

        # Rolling statistics
        past_6 = recent_aqi_values[-6:] if len(recent_aqi_values) >= 6 else recent_aqi_values
        past_24 = recent_aqi_values[-24:] if len(recent_aqi_values) >= 24 else recent_aqi_values

        mean_6 = float(np.mean(past_6))
        mean_24 = float(np.mean(past_24))
        std_24 = float(np.std(past_24)) if len(past_24) > 1 else 5.0

        feat_row = {
            "hour": current_hour,
            "dayofweek": day_of_week,
            "aqi_rolling_mean_6h": mean_6,
            "aqi_rolling_mean_24h": mean_24,
            "aqi_rolling_std_24h": std_24,
            "pm2_5_lag_1": latest_aqi * 0.4,
            "pm2_5_lag_2": latest_aqi * 0.4,
            "pm2_5_lag_3": latest_aqi * 0.4,
        }
        feat_row.update(lags)

        feat_df = pd.DataFrame([[feat_row.get(c, 0.0) for c in feature_cols]], columns=feature_cols)

        for h in range(1, 7):
            h_key = f"h{h}"
            if h_key in models_dict:
                h_info = models_dict[h_key]
                model = h_info["model"]
                pred = float(model.predict(feat_df)[0])
                pred_clean = max(1, round(pred, 1))
                forecast_points.append({
                    "horizon_hours": h,
                    "predicted_aqi": pred_clean,
                    "model_used": h_info.get("algorithm", "ML Forecaster"),
                    "source": "PREDICTED (ML)",
                })
            else:
                # Fallback persistence
                forecast_points.append({
                    "horizon_hours": h,
                    "predicted_aqi": round(latest_aqi, 1),
                    "model_used": "Persistence Baseline",
                    "source": "PREDICTED (Baseline)",
                })
    else:
        # Fallback persistence baseline
        for h in range(1, 7):
            forecast_points.append({
                "horizon_hours": h,
                "predicted_aqi": round(latest_aqi, 1),
                "model_used": "Persistence Baseline",
                "source": "PREDICTED (Baseline)",
            })

    return {
        "status": "ok",
        "current_aqi": latest_aqi,
        "forecast": forecast_points,
        "source": "PREDICTED (ML Multi-Horizon)",
    }
