"""
Unit tests for the Risk Advisory Engine (risk_engine.py).

Validates:
1. All 7 health profiles produce valid, tailored guidance
2. CPCB AQI categories and particulate breakpoints
3. Profile input NEVER modifies measured/evaluated pollutant values
4. Missing, None, negative, and malformed AQI inputs handled safely
5. Standard educational disclaimer is consistently included
"""

import pytest
import risk_engine


def test_list_profiles():
    profiles = risk_engine.list_profiles()
    assert len(profiles) == 7
    ids = {p["id"] for p in profiles}
    expected = {
        "healthy_adult",
        "older_adult",
        "child",
        "asthma",
        "bronchitis",
        "copd",
        "cardiovascular",
    }
    assert ids == expected


@pytest.mark.parametrize(
    "aqi,expected_cat",
    [
        (0, "Good"),
        (25, "Good"),
        (50, "Good"),
        (51, "Satisfactory"),
        (100, "Satisfactory"),
        (101, "Moderate"),
        (200, "Moderate"),
        (201, "Poor"),
        (300, "Poor"),
        (301, "Very Poor"),
        (400, "Very Poor"),
        (401, "Severe"),
        (500, "Severe"),
    ],
)
def test_aqi_breakpoints(aqi, expected_cat):
    cat = risk_engine.get_aqi_category(aqi)
    assert cat is not None
    assert cat["name"] == expected_cat


def test_evaluate_all_7_profiles():
    all_profiles = [
        "healthy_adult",
        "older_adult",
        "child",
        "asthma",
        "bronchitis",
        "copd",
        "cardiovascular",
    ]
    for pid in all_profiles:
        result = risk_engine.evaluate_risk(
            aqi=120,
            pm2_5=42.5,
            pm10=78.0,
            profile_id=pid,
            activity_level="outdoor_exercise",
        )
        assert result["status"] == "ok"
        assert result["category"] == "Moderate"
        assert result["aqi_value"] == 120
        assert result["pollutants_evaluated"]["pm2_5"] == 42.5
        assert result["pollutants_evaluated"]["pm10"] == 78.0
        assert result["profile"]["id"] == pid
        assert len(result["tailored_precautions"]) > 0
        assert result["disclaimer"] == risk_engine.DISCLAIMER_TEXT


def test_profile_never_alters_pollutant_values():
    """CRITICAL TEST: The health profile must NEVER alter the pollutant values or AQI."""
    base_aqi = 85
    base_pm25 = 28.4
    base_pm10 = 60.1

    res_healthy = risk_engine.evaluate_risk(
        aqi=base_aqi, pm2_5=base_pm25, pm10=base_pm10, profile_id="healthy_adult"
    )
    res_copd = risk_engine.evaluate_risk(
        aqi=base_aqi, pm2_5=base_pm25, pm10=base_pm10, profile_id="copd"
    )

    # Pollutant values and AQI MUST be identical
    assert res_healthy["aqi_value"] == res_copd["aqi_value"] == base_aqi
    assert (
        res_healthy["pollutants_evaluated"]
        == res_copd["pollutants_evaluated"]
        == {"cpcb_aqi": base_aqi, "pm2_5": base_pm25, "pm10": base_pm10}
    )
    # Category name MUST be identical (it reflects the AQI)
    assert res_healthy["category"] == res_copd["category"] == "Satisfactory"

    # Only guidance and risk level change based on vulnerability!
    assert res_healthy["risk_level"] != res_copd["risk_level"]
    assert res_healthy["tailored_precautions"] != res_copd["tailored_precautions"]


def test_edge_cases_missing_and_none():
    # AQI is None (data unavailable)
    res = risk_engine.evaluate_risk(aqi=None, pm2_5=12.0)
    assert res["status"] == "unavailable"
    assert res["category"] == "Unavailable"
    assert res["risk_level"] == "Unknown"
    assert res["aqi_value"] is None
    assert len(res["tailored_precautions"]) > 0
    assert risk_engine.DISCLAIMER_TEXT in res["disclaimer"]


def test_edge_cases_invalid_aqi():
    # Negative AQI
    res_neg = risk_engine.evaluate_risk(aqi=-10)
    assert res_neg["status"] == "invalid_value"
    assert res_neg["category"] == "Invalid"

    # String non-numeric AQI
    res_str = risk_engine.evaluate_risk(aqi="bad_data")
    assert res_str["status"] == "invalid_value"


def test_extreme_severe_aqi():
    res = risk_engine.evaluate_risk(aqi=450, profile_id="asthma")
    assert res["status"] == "ok"
    assert res["category"] == "Severe"
    assert res["risk_level"] == "Very High"
    assert "N95" in res["mask_recommendation"]


@pytest.mark.parametrize(
    "pm2_5,pm10,expected",
    [
        (30, None, 50),
        (60, None, 100),
        (None, 50, 50),
        (None, 100, 100),
        (280, 500, 500),
        (None, None, None),
        (-1, None, None),
    ],
)
def test_cpcb_aqi_from_particulate_breakpoints(pm2_5, pm10, expected):
    assert risk_engine.calculate_cpcb_aqi(pm2_5, pm10) == expected
