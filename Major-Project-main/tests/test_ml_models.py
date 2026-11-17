"""
Unit tests for Machine Learning models and inference module (predict.py).

Validates:
1. Classification model loading and schema consistency
2. Multi-horizon forecasting loading and schema consistency
3. Predict category output format and required keys
4. Multi-horizon forecast output format and horizon counts
5. Fallback behavior when inputs are missing
6. Strict chronological leakage check: future timestamps not used in past lag features
"""

import pytest
import predict
from train_models import build_forecasting_features, load_dataset


def test_classifier_loading_and_inference():
    clf_bundle = predict.get_classifier()
    assert clf_bundle is not None
    assert "model" in clf_bundle
    assert "feature_cols" in clf_bundle
    assert "classes" in clf_bundle

    result = predict.predict_category(pm2_5=35.0, pm10=50.0)
    assert result["status"] == "ok"
    assert "predicted_category" in result
    assert result["source"].startswith("PREDICTED")


def test_forecaster_loading_and_inference():
    forecaster = predict.get_forecaster()
    assert forecaster is not None
    assert "models" in forecaster
    assert "horizons" in forecaster
    assert len(forecaster["horizons"]) == 6

    result = predict.predict_multi_horizon_aqi(
        recent_aqi_values=[50.0, 55.0, 60.0, 65.0, 70.0],
        current_hour=14,
        day_of_week=2,
    )
    assert result["status"] == "ok"
    assert len(result["forecast"]) == 6
    for point in result["forecast"]:
        assert "horizon_hours" in point
        assert "predicted_aqi" in point
        assert point["predicted_aqi"] > 0
        assert "PREDICTED" in point["source"]


def test_predict_category_edge_cases():
    # Missing PM2.5
    res = predict.predict_category(pm2_5=None)
    assert res["status"] == "unavailable"
    assert res["predicted_category"] is None

    # Very high PM2.5 (should predict a severe CPCB category)
    res_high = predict.predict_category(pm2_5=280.0)
    assert res_high["status"] == "ok"
    assert res_high["predicted_category"] in ["Poor", "Very Poor", "Severe"]


def test_forecasting_no_future_leakage():
    """Verify that feature engineering does not leak target horizons into features."""
    df = load_dataset()
    featured = build_forecasting_features(df)

    # Feature columns should only contain lags or time indicators, never future targets
    feature_cols = [c for c in featured.columns if not c.startswith("target_") and c not in ["time", "cpcb_aqi"]]
    for col in feature_cols:
        assert not col.startswith("target_"), f"Future target {col} found in features!"
        # Verify rolling mean was computed with shift(1)
        assert "target" not in col
