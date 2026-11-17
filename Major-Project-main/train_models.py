"""
Machine Learning Training and Empirical Evaluation Pipeline.

Tasks:
1. Current Air Quality Category Classification:
   - Compares: Rule-Based Baseline, Decision Tree, Random Forest, Gradient Boosting.
   - Metrics: Accuracy, Precision (macro), Recall (macro), Macro-F1, Confusion Matrix, Training Time.
   - Explains clearly: If target is derived from CPCB breakpoints, the model reproduces
     the rule rather than discovering independent disease risk.
2. Independent 1-6 Hour Multi-Horizon Forecasting:
   - Evaluates: Persistence Baseline, Linear Regression, Random Forest, Extra Trees, Gradient Boosting.
   - Multi-horizon evaluation: Horizons h=1, 2, 3, 4, 5, 6 hours ahead evaluated separately.
   - Strict chronological split: No future lookahead or data leakage.
   - Metrics: MAE, RMSE, R² for each horizon.
3. Save Model Artifacts & Real Metrics:
   - Saves CSV and JSON evaluation results for display in dashboard.
"""

import json
import time
from pathlib import Path
import numpy as np
import pandas as pd
import joblib

from sklearn.tree import DecisionTreeClassifier
from sklearn.ensemble import (
    RandomForestClassifier,
    GradientBoostingClassifier,
    RandomForestRegressor,
    ExtraTreesRegressor,
    GradientBoostingRegressor,
)
from sklearn.linear_model import LinearRegression
from sklearn.metrics import (
    accuracy_score,
    precision_score,
    recall_score,
    f1_score,
    confusion_matrix,
    mean_absolute_error,
    mean_squared_error,
    r2_score,
)
from risk_engine import calculate_cpcb_aqi

DATA_PATH = Path("data/openmeteo_yelahanka_hourly_history.csv")
MODELS_DIR = Path("models")


def load_dataset() -> pd.DataFrame:
    """Load and prepare hourly time series dataset."""
    if not DATA_PATH.exists():
        raise FileNotFoundError(f"Dataset not found at {DATA_PATH}. Run collect_air_quality_history.py first.")

    df = pd.read_csv(DATA_PATH)
    df["time"] = pd.to_datetime(df["time"])
    df = df.sort_values("time").reset_index(drop=True)

    # Convert pollutant columns to numeric
    numeric_cols = ["pm2_5", "pm10", "carbon_monoxide", "nitrogen_dioxide", "sulphur_dioxide", "ozone"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")

    df["cpcb_aqi"] = df.apply(
        lambda row: calculate_cpcb_aqi(row.get("pm2_5"), row.get("pm10")),
        axis=1,
    )
    df = df.dropna(subset=["cpcb_aqi", "pm2_5"]).reset_index(drop=True)
    return df


def categorize_aqi(aqi: float) -> str:
    """Map numeric CPCB AQI to category string."""
    if aqi <= 50:
        return "Good"
    elif aqi <= 100:
        return "Satisfactory"
    elif aqi <= 200:
        return "Moderate"
    elif aqi <= 300:
        return "Poor"
    elif aqi <= 400:
        return "Very Poor"
    return "Severe"


# =====================================================================
# TASK 1: AIR QUALITY CATEGORY CLASSIFICATION
# =====================================================================

def run_classification_task(df: pd.DataFrame):
    """Train and evaluate classification models for current air quality category."""
    print("\n" + "=" * 60)
    print("TASK 1: Current Air Quality Category Classification")
    print("=" * 60)

    # Derive target
    df = df.copy()
    df["aqi_category"] = df["cpcb_aqi"].apply(categorize_aqi)

    feature_cols = [c for c in ["pm2_5", "pm10"] if c in df.columns]
    X = df[feature_cols].copy()
    y = df["aqi_category"].copy()

    # Chronological train/test split (80% train, 20% test)
    split_idx = int(len(df) * 0.8)
    X_train, X_test = X.iloc[:split_idx], X.iloc[split_idx:]
    y_train, y_test = y.iloc[:split_idx], y.iloc[split_idx:]

    classes = sorted(list(y.unique()))
    print(f"Dataset size: {len(df)} rows. Train: {len(X_train)}, Test: {len(X_test)}")
    print(f"Target categories present: {classes}")

    # Baseline: CPCB particulate sub-indices determine the AQI category.
    def rule_based_predict(X_subset):
        preds = []
        for _, row in X_subset.iterrows():
            aqi = calculate_cpcb_aqi(row.get("pm2_5"), row.get("pm10"))
            preds.append(categorize_aqi(aqi) if aqi is not None else "Unavailable")
        return preds

    models = {
        "Rule-Based Baseline (CPCB PM Breakpoints)": None,
        "Decision Tree": DecisionTreeClassifier(max_depth=5, random_state=42),
        "Random Forest": RandomForestClassifier(n_estimators=100, max_depth=8, random_state=42),
        "Gradient Boosting": GradientBoostingClassifier(n_estimators=80, max_depth=4, random_state=42),
    }

    results = []
    best_f1 = -1
    best_model = None
    best_name = ""
    conf_matrix_dict = {}

    for name, clf in models.items():
        t0 = time.time()
        if clf is None:
            # Rule based
            y_pred = rule_based_predict(X_test)
            train_time = 0.001
        else:
            clf.fit(X_train, y_train)
            train_time = time.time() - t0
            y_pred = clf.predict(X_test)

            if f1_score(y_test, y_pred, average="macro", zero_division=0) > best_f1:
                best_f1 = f1_score(y_test, y_pred, average="macro", zero_division=0)
                best_model = clf
                best_name = name

        acc = accuracy_score(y_test, y_pred)
        prec = precision_score(y_test, y_pred, average="macro", zero_division=0)
        rec = recall_score(y_test, y_pred, average="macro", zero_division=0)
        f1 = f1_score(y_test, y_pred, average="macro", zero_division=0)
        cm = confusion_matrix(y_test, y_pred, labels=classes).tolist()

        conf_matrix_dict[name] = {
            "classes": classes,
            "matrix": cm,
        }

        row = {
            "model": name,
            "accuracy": round(float(acc), 4),
            "precision_macro": round(float(prec), 4),
            "recall_macro": round(float(rec), 4),
            "macro_f1": round(float(f1), 4),
            "training_time_sec": round(float(train_time), 4),
            "test_samples": len(X_test),
        }
        results.append(row)
        print(f"[{name}] Acc: {acc:.4f} | Prec: {prec:.4f} | Rec: {rec:.4f} | F1: {f1:.4f} | Time: {train_time:.3f}s")

    # Save best classifier
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    if best_model is not None:
        clf_artifact = {
            "model": best_model,
            "model_name": best_name,
            "feature_cols": feature_cols,
            "classes": classes,
        }
        joblib.dump(clf_artifact, MODELS_DIR / "aqi_classifier.joblib")
        print(f"Saved best classifier '{best_name}' to {MODELS_DIR / 'aqi_classifier.joblib'}")

    with open(MODELS_DIR / "classification_metrics.json", "w", encoding="utf-8") as f:
        json.dump({
            "task": "Current Air Quality Category Classification",
            "methodology_note": "AQI is estimated from hourly modelled PM2.5 and PM10 using CPCB breakpoints. These categories are rule-derived and do not represent clinical risk predictions.",
            "classes": classes,
            "features": feature_cols,
            "results": results,
            "confusion_matrices": conf_matrix_dict,
        }, f, indent=2)

    return results


# =====================================================================
# TASK 2: MULTI-HORIZON TIME SERIES FORECASTING (1-6 HOURS)
# =====================================================================

def build_forecasting_features(df: pd.DataFrame) -> pd.DataFrame:
    """Generate lag features and rolling aggregations without data leakage."""
    data = df.copy()

    # Time-based features
    data["hour"] = data["time"].dt.hour
    data["dayofweek"] = data["time"].dt.dayofweek

    # Lag features for AQI
    for lag in [1, 2, 3, 6, 12, 24]:
        data[f"aqi_lag_{lag}"] = data["cpcb_aqi"].shift(lag)

    # Lag features for PM2.5
    for lag in [1, 2, 3]:
        data[f"pm2_5_lag_{lag}"] = data["pm2_5"].shift(lag)

    # Rolling window statistics (computed strictly on past lags, shift by 1 to prevent leakage)
    data["aqi_rolling_mean_6h"] = data["cpcb_aqi"].shift(1).rolling(window=6).mean()
    data["aqi_rolling_mean_24h"] = data["cpcb_aqi"].shift(1).rolling(window=24).mean()
    data["aqi_rolling_std_24h"] = data["cpcb_aqi"].shift(1).rolling(window=24).std()

    # Future targets for horizons 1 through 6
    for h in range(1, 7):
        data[f"target_h{h}"] = data["cpcb_aqi"].shift(-h)

    # Drop NaN rows generated by lagging and horizon lookaheads
    data = data.dropna().reset_index(drop=True)
    return data


def run_forecasting_task(df: pd.DataFrame):
    """Train and evaluate multi-horizon forecasting models (1 to 6 hours ahead)."""
    print("\n" + "=" * 60)
    print("TASK 2: Independent 1-6 Hour Multi-Horizon Forecasting")
    print("=" * 60)

    featured_data = build_forecasting_features(df)
    feature_cols = [c for c in featured_data.columns if c.startswith(("aqi_lag_", "pm2_5_lag_", "aqi_rolling_")) or c in ["hour", "dayofweek"]]

    # Chronological train/test split (80% train, 20% test)
    split_idx = int(len(featured_data) * 0.8)
    train_df = featured_data.iloc[:split_idx]
    test_df = featured_data.iloc[split_idx:]

    X_train = train_df[feature_cols]
    X_test = test_df[feature_cols]

    print(f"Forecasting samples: {len(featured_data)} | Train: {len(train_df)} | Test: {len(test_df)}")
    print(f"Features ({len(feature_cols)}): {feature_cols}")

    horizons = [1, 2, 3, 4, 5, 6]
    candidate_algorithms = {
        "Persistence Baseline": "persistence",
        "Linear Regression": LinearRegression(),
        "Random Forest": RandomForestRegressor(n_estimators=100, max_depth=8, random_state=42),
        "Extra Trees": ExtraTreesRegressor(n_estimators=100, max_depth=8, random_state=42),
        "Gradient Boosting": GradientBoostingRegressor(n_estimators=80, max_depth=4, random_state=42),
    }

    all_horizon_results = {}
    summary_rows = []
    saved_models = {}

    for h in horizons:
        print(f"\n--- Horizon h = {h} hour(s) ahead ---")
        y_train = train_df[f"target_h{h}"]
        y_test = test_df[f"target_h{h}"]

        horizon_eval = []
        best_rmse = float("inf")
        best_model_obj = None
        best_algo_name = ""

        for name, model in candidate_algorithms.items():
            t0 = time.time()
            if model == "persistence":
                # Persistence: predict current value (aqi_lag_1 is t-1, but current t is X_test['aqi_lag_1'] shifted or lag 0)
                # In feature set, aqi_lag_1 represents the most recently completed hour t
                y_pred = X_test["aqi_lag_1"].values
                train_time = 0.0001
            else:
                model.fit(X_train, y_train)
                train_time = time.time() - t0
                y_pred = model.predict(X_test)

                if mean_squared_error(y_test, y_pred) < best_rmse:
                    best_rmse = mean_squared_error(y_test, y_pred)
                    best_model_obj = model
                    best_algo_name = name

            mae = mean_absolute_error(y_test, y_pred)
            rmse = np.sqrt(mean_squared_error(y_test, y_pred))
            r2 = r2_score(y_test, y_pred)

            eval_dict = {
                "horizon_hours": h,
                "model": name,
                "MAE": round(float(mae), 3),
                "RMSE": round(float(rmse), 3),
                "R2": round(float(r2), 4),
                "train_time_sec": round(float(train_time), 4),
            }
            horizon_eval.append(eval_dict)
            summary_rows.append(eval_dict)

            print(f"  [{name:22s}] MAE: {mae:6.2f} | RMSE: {rmse:6.2f} | R2: {r2:6.3f}")

        all_horizon_results[f"horizon_{h}h"] = horizon_eval

        # Save best model for this horizon
        if best_model_obj is not None:
            saved_models[f"h{h}"] = {
                "horizon": h,
                "algorithm": best_algo_name,
                "model": best_model_obj,
            }

    # Save best models artifact
    MODELS_DIR.mkdir(parents=True, exist_ok=True)
    forecaster_artifact = {
        "models": saved_models,
        "feature_cols": feature_cols,
        "horizons": horizons,
    }
    joblib.dump(forecaster_artifact, MODELS_DIR / "aqi_forecaster.joblib")
    print(f"\nSaved multi-horizon forecasting bundle to {MODELS_DIR / 'aqi_forecaster.joblib'}")

    # Save summary dataframe to CSV
    summary_df = pd.DataFrame(summary_rows)
    summary_df.to_csv(MODELS_DIR / "model_comparison.csv", index=False)
    print(f"Saved real comparative metrics to {MODELS_DIR / 'model_comparison.csv'}")

    # Build representative actual vs predicted points for dashboard plotting
    # Use h=1 and h=6 test slice
    h1_test_y = test_df["target_h1"].iloc[:50].tolist()
    h1_model = saved_models["h1"]["model"]
    h1_pred_y = h1_model.predict(X_test.iloc[:50]).round(1).tolist()
    test_timestamps = test_df["time"].dt.strftime("%Y-%m-%d %H:%M").iloc[:50].tolist()

    with open(MODELS_DIR / "evaluation_results.json", "w", encoding="utf-8") as f:
        json.dump({
            "task": "Multi-Horizon CPCB AQI Estimate Forecasting",
            "horizons": horizons,
            "features_used": feature_cols,
            "train_samples": len(train_df),
            "test_samples": len(test_df),
            "results_by_horizon": all_horizon_results,
            "plot_sample": {
                "timestamps": test_timestamps,
                "actual": h1_test_y,
                "predicted": h1_pred_y,
                "residuals": [round(a - p, 2) for a, p in zip(h1_test_y, h1_pred_y)],
            },
        }, f, indent=2)

    return summary_rows


if __name__ == "__main__":
    df = load_dataset()
    cls_res = run_classification_task(df)
    fct_res = run_forecasting_task(df)
    print("\nTraining & evaluation completed successfully!")
