"""
Health Risk Advisory Engine.

Translates air quality metrics (specifically CPCB AQI and pollutant concentrations)
into profile-specific health guidance and actionable precautions.

Design Rules & Non-Negotiables:
1. Standards: Uses CPCB AQI breakpoints for available pollutant concentrations.
2. The user profile changes the GUIDANCE ONLY. It NEVER modifies measured
   or estimated pollutant values, sensor raw readings, or the AQI index itself.
3. No diagnostic or individual disease incidence claims:
   This engine provides precautionary, rule-based environmental health guidance.
4. Transparent Disclaimer: Visible educational disclaimer stating this is
   an engineering prototype, not a medical device.
"""

from typing import Dict, Any, List, Optional

# Standard Educational & Medical Disclaimer
DISCLAIMER_TEXT = (
    "EDUCATIONAL ENVIRONMENTAL MONITORING PROTOTYPE: This advisory is generated for "
    "general informational and educational purposes based on ambient air quality estimates. "
    "It is NOT a medical device and does NOT provide clinical diagnoses, personalized medical "
    "risk probabilities, or treatment prescriptions. Individuals with respiratory, cardiovascular, "
    "or other underlying conditions should adhere strictly to their physician's medical action plan."
)

# Supported Health Profiles
PROFILES = {
    "healthy_adult": {
        "id": "healthy_adult",
        "name": "Healthy Adult",
        "description": "Adult without diagnosed chronic respiratory or cardiovascular illness.",
        "sensitivity_level": "standard",
    },
    "older_adult": {
        "id": "older_adult",
        "name": "Older Adult (65+)",
        "description": "Seniors with decreased physiological lung reserve or age-related sensitivity.",
        "sensitivity_level": "elevated",
    },
    "child": {
        "id": "child",
        "name": "Child / Adolescent",
        "description": "Developing lungs with higher breathing rates relative to body mass.",
        "sensitivity_level": "elevated",
    },
    "asthma": {
        "id": "asthma",
        "name": "Asthma Patient",
        "description": "Hyperreactive airways prone to bronchospasm from particulate exposure.",
        "sensitivity_level": "high",
    },
    "bronchitis": {
        "id": "bronchitis",
        "name": "Chronic Bronchitis Patient",
        "description": "Persistent mucus hypersecretion and chronic airway inflammation.",
        "sensitivity_level": "high",
    },
    "copd": {
        "id": "copd",
        "name": "COPD Patient",
        "description": "Chronic obstructive pulmonary disease with permanent airflow limitation.",
        "sensitivity_level": "critical",
    },
    "cardiovascular": {
        "id": "cardiovascular",
        "name": "Cardiovascular Disease Patient",
        "description": "Coronary artery disease, hypertension, or arrhythmia sensitive to vascular stress.",
        "sensitivity_level": "high",
    },
}

# CPCB AQI Categories
AQI_CATEGORIES = [
    {
        "name": "Good",
        "min_aqi": 0,
        "max_aqi": 50,
        "color": "#10b981",  # Emerald Green
        "description": "Air quality is satisfactory and poses little or no health risk.",
    },
    {
        "name": "Satisfactory",
        "min_aqi": 51,
        "max_aqi": 100,
        "color": "#f59e0b",  # Amber / Yellow
        "description": "Air quality is acceptable; sensitive individuals may experience minor discomfort.",
    },
    {
        "name": "Moderate",
        "min_aqi": 101,
        "max_aqi": 200,
        "color": "#f97316",  # Orange
        "description": "Sensitive individuals may experience breathing discomfort during prolonged exposure.",
    },
    {
        "name": "Poor",
        "min_aqi": 201,
        "max_aqi": 300,
        "color": "#ef4444",  # Red
        "description": "People may experience breathing discomfort after prolonged exposure.",
    },
    {
        "name": "Very Poor",
        "min_aqi": 301,
        "max_aqi": 400,
        "color": "#8b5cf6",  # Purple
        "description": "Prolonged exposure may cause respiratory illness, including in otherwise healthy people.",
    },
    {
        "name": "Severe",
        "min_aqi": 401,
        "max_aqi": 500,
        "color": "#881337",  # Deep Maroon
        "description": "Even healthy people may experience respiratory effects; people with existing conditions may be more seriously affected.",
    },
]


def calculate_cpcb_aqi(
    pm2_5: Optional[float] = None,
    pm10: Optional[float] = None,
) -> Optional[int]:
    """Estimate CPCB AQI from available PM2.5 and PM10 concentrations."""
    breakpoints = {
        "pm2_5": ((0, 30, 0, 50), (31, 60, 51, 100), (61, 90, 101, 200),
                  (91, 120, 201, 300), (121, 250, 301, 400), (251, 500, 401, 500)),
        "pm10": ((0, 50, 0, 50), (51, 100, 51, 100), (101, 250, 101, 200),
                 (251, 350, 201, 300), (351, 430, 301, 400), (431, 500, 401, 500)),
    }

    subindices = []
    for pollutant, concentration in (("pm2_5", pm2_5), ("pm10", pm10)):
        if concentration is None:
            continue
        try:
            value = float(concentration)
        except (TypeError, ValueError):
            continue
        if value < 0:
            continue

        ranges = breakpoints[pollutant]
        maximum = ranges[-1][1]
        if value > maximum:
            subindices.append(500)
            continue

        for concentration_low, concentration_high, aqi_low, aqi_high in ranges:
            if value <= concentration_high:
                index = (
                    (aqi_high - aqi_low)
                    * (value - concentration_low)
                    / (concentration_high - concentration_low)
                    + aqi_low
                )
                subindices.append(int(round(index)))
                break

    return max(subindices) if subindices else None


def get_aqi_category(aqi_value: Optional[int]) -> Optional[Dict[str, Any]]:
    """Determine the CPCB AQI category metadata for a given AQI value."""
    if aqi_value is None:
        return None
    try:
        val = int(round(float(aqi_value)))
    except (ValueError, TypeError):
        return None

    if val < 0:
        return None

    for cat in AQI_CATEGORIES:
        if cat["min_aqi"] <= val <= cat["max_aqi"]:
            return cat

    return None


def evaluate_risk(
    aqi: Optional[int] = None,
    pm2_5: Optional[float] = None,
    pm10: Optional[float] = None,
    profile_id: str = "healthy_adult",
    activity_level: str = "moderate",
    respiratory_condition: Optional[str] = None,
    age_group: Optional[str] = None,
    has_respiratory_problem: Optional[Any] = None,
) -> Dict[str, Any]:
    """Evaluate health risk and produce tailored advisory guidance.

    Args:
        aqi: CPCB AQI estimate (integer 0-500)
        pm2_5: PM2.5 concentration in µg/m³ (optional context)
        pm10: PM10 concentration in µg/m³ (optional context)
        profile_id: One of the 7 supported profile keys
        activity_level: "low", "moderate", "vigorous", or "outdoor_exercise"
        respiratory_condition: Optional specific condition ("asthma", "bronchitis", "copd", "cardiovascular", "none")
        age_group: Optional age category ("child", "adult", "older_adult")
        has_respiratory_problem: Optional boolean / string indicating respiratory status

    Returns:
        Structured dictionary with risk category, risk factor score, tailored guidance,
        precautions, mask recommendation, and disclaimer.
    """
    # 1. Resolve effective profile from explicit respiratory_condition or profile_id
    effective_id = profile_id
    if respiratory_condition:
        cond_map = {
            "asthma": "asthma",
            "bronchitis": "bronchitis",
            "copd": "copd",
            "cardiovascular": "cardiovascular",
            "none": "healthy_adult",
        }
        effective_id = cond_map.get(respiratory_condition.lower(), effective_id)
        if respiratory_condition.lower() == "none":
            if age_group == "child":
                effective_id = "child"
            elif age_group == "older_adult":
                effective_id = "older_adult"

    elif has_respiratory_problem is False and effective_id in ("asthma", "bronchitis", "copd"):
        effective_id = "healthy_adult"

    profile = PROFILES.get(effective_id, PROFILES["healthy_adult"])
    pid = profile["id"]

    # 2. Check for missing / unavailable data
    if aqi is None:
        return {
            "status": "unavailable",
            "category": "Unavailable",
            "color": "#6b7280",
            "risk_level": "Unknown",
            "aqi_value": None,
            "pollutants_evaluated": {
                "cpcb_aqi": None,
                "pm2_5": pm2_5,
                "pm10": pm10,
            },
            "profile": profile,
            "activity_level": activity_level,
            "outdoor_recommendation": "Ambient air quality data is currently unavailable.",
            "tailored_precautions": [
                "Air quality data feed is currently offline or unreachable.",
                "Individuals with known respiratory or cardiac conditions should proceed with routine personal precautions.",
                "Check back once telemetry or API connection is re-established.",
            ],
            "mask_recommendation": "Standard precautions as needed.",
            "disclaimer": DISCLAIMER_TEXT,
        }

    # 3. Categorize CPCB AQI
    cat = get_aqi_category(aqi)
    if cat is None:
        return {
            "status": "invalid_value",
            "category": "Invalid",
            "color": "#6b7280",
            "risk_level": "Unknown",
            "aqi_value": aqi,
            "pollutants_evaluated": {"cpcb_aqi": aqi, "pm2_5": pm2_5, "pm10": pm10},
            "profile": profile,
            "activity_level": activity_level,
            "outdoor_recommendation": "Invalid AQI value received.",
            "tailored_precautions": ["Verify sensor or API input formatting."],
            "mask_recommendation": "Not specified.",
            "disclaimer": DISCLAIMER_TEXT,
        }

    cat_name = cat["name"]
    color = cat["color"]

    # 4. Generate profile-tailored guidance
    precautions: List[str] = []
    outdoor_rec = ""
    mask_rec = "Not required"
    risk_level = "Low"

    # Base assessment per category
    if cat_name == "Good":
        risk_level = "Low"
        outdoor_rec = "Air quality is ideal for all outdoor activities."
        precautions.append("Enjoy outdoor recreation, sports, and ventilation.")
        if pid in ("asthma", "copd", "bronchitis"):
            precautions.append("Carry routine inhaler as standard protocol, though ambient trigger risk is low.")

    elif cat_name == "Satisfactory":
        if pid in ("asthma", "bronchitis", "copd"):
            risk_level = "Elevated"
            outdoor_rec = "Routine outdoor activity is generally acceptable; monitor for symptoms."
            precautions.append("Keep prescribed rescue medication accessible during extended outdoor activity.")
        else:
            risk_level = "Low"
            outdoor_rec = "Routine outdoor activity is generally acceptable."
            precautions.append("Sensitive individuals should reduce prolonged exertion if symptoms occur.")

    elif cat_name == "Moderate":
        if pid in ("asthma", "bronchitis", "copd"):
            risk_level = "High"
            outdoor_rec = "Reduce prolonged or vigorous outdoor exertion and monitor for symptoms."
            precautions.append("Keep prescribed rescue medication accessible.")
        else:
            risk_level = "Moderate"
            outdoor_rec = "Reduce prolonged or strenuous outdoor exertion."
            precautions.append("Sensitive individuals should limit prolonged outdoor exposure.")

    elif cat_name == "Poor":
        if pid in ("asthma", "bronchitis", "copd"):
            risk_level = "High"
            outdoor_rec = "Significantly limit prolonged or vigorous outdoor exertion. Shift workouts indoors."
            precautions.append("Pre-medicate with prescribed preventive inhaler if advised by your physician.")
            precautions.append("Keep windows closed during peak traffic hours.")
            precautions.append("Seek medical consultation immediately if dyspnea fails to resolve.")
            mask_rec = "N95 / FFP2 respirator recommended if staying outdoors > 30 minutes."
        elif pid in ("older_adult", "child", "cardiovascular"):
            risk_level = "Elevated"
            outdoor_rec = "Reduce prolonged outdoor endurance activities and take frequent rest intervals."
            precautions.append("Avoid heavy aerobic workouts outdoors; prefer climate-controlled indoor spaces.")
            precautions.append("Monitor blood pressure and pulse if managing cardiovascular disease.")
            mask_rec = "Well-fitting mask recommended during peak commute or heavy outdoor exposure."
        else:
            risk_level = "Moderate"
            outdoor_rec = "Most people can remain active outdoors; sensitive persons should moderate heavy exertion."
            precautions.append("Consider reducing multi-hour intense outdoor workouts.")

    elif cat_name == "Very Poor":
        risk_level = "High"
        mask_rec = "N95 / FFP2 respirator strongly advised for any outdoor transit."
        if pid in ("asthma", "bronchitis", "copd", "cardiovascular", "older_adult", "child"):
            risk_level = "Very High"
            outdoor_rec = "Avoid outdoor physical activities completely. Stay in filtered indoor environments."
            precautions.append("Keep windows sealed and operate indoor HEPA filtration if available.")
            precautions.append("Avoid active or passive tobacco smoke and other indoor combustion sources.")
            precautions.append("Have rescue medication within arm's reach.")
        else:
            outdoor_rec = "Avoid prolonged or heavy exertion outdoors. Postpone strenuous sports."
            precautions.append("Move endurance runs, cycling, and sports indoors.")
            precautions.append("Keep residential windows and doors closed to minimize particulate infiltration.")

    elif cat_name == "Severe":
        risk_level = "Very High"
        outdoor_rec = "Severe pollution warning: avoid strenuous outdoor activities and minimize exposure."
        mask_rec = "A well-fitting N95 / FFP2 respirator may reduce particulate exposure outdoors."
        precautions.append("Keep all residential ventilation closed and utilize air purification.")
        precautions.append("Vulnerable groups (respiratory/cardiac patients, seniors, children) should remain strictly indoors.")
        if pid in ("asthma", "copd", "bronchitis", "cardiovascular"):
            precautions.append("Contact your healthcare provider promptly if experiencing coughing, chest tightness, or dizziness.")

    # Calculate Personal Risk Factor Index (0-100) & Vulnerability Factor Breakdown
    vuln_multipliers = {
        "healthy_adult": 1.0,
        "child": 1.25,
        "older_adult": 1.3,
        "cardiovascular": 1.45,
        "asthma": 1.55,
        "bronchitis": 1.6,
        "copd": 1.8,
    }
    act_multipliers = {
        "low": 0.85,
        "moderate": 1.0,
        "vigorous": 1.35,
        "outdoor_exercise": 1.35,
    }
    v_mult = vuln_multipliers.get(pid, 1.0)
    a_mult = act_multipliers.get(activity_level, 1.0)
    base_aqi_score = min(100.0, (float(aqi) / 500.0) * 100.0)
    computed_risk_score = min(100, max(5, int(round(base_aqi_score * v_mult * a_mult))))

    condition_explanations = {
        "asthma": "Airway hyper-responsiveness: Inhaled fine particulates (PM2.5) stimulate bronchial hyperreactivity and provoke acute bronchospasms.",
        "bronchitis": "Chronic epithelial inflammation: Particulate and gaseous irritants aggravate bronchial mucus secretion and induce chronic cough episodes.",
        "copd": "Permanent airflow obstruction: Ambient pollutants severely accelerate gas-exchange impairment and clinical exacerbation frequency.",
        "cardiovascular": "Systemic endothelial stress: Fine particles induce autonomic imbalance, microvascular vasoconstriction, and arterial pressure spikes.",
        "child": "Immature respiratory defense: High ventilation rate relative to lung volume amplifies effective pollutant deposition in developing airways.",
        "older_adult": "Diminished physiological reserve: Decreased mucociliary clearance and age-associated pulmonary compliance amplify vulnerability.",
        "healthy_adult": "Standard physiological baseline: Intact mucociliary clearance and normal alveolar gas diffusion capacity.",
    }
    explanation = condition_explanations.get(pid, "General environmental exposure assessment.")

    return {
        "status": "ok",
        "category": cat_name,
        "color": color,
        "risk_level": risk_level,
        "risk_factor_score": computed_risk_score,
        "risk_factor_multiplier": round(v_mult * a_mult, 2),
        "risk_factor_explanation": explanation,
        "aqi_value": int(round(float(aqi))),
        "pollutants_evaluated": {
            "cpcb_aqi": int(round(float(aqi))),
            "pm2_5": pm2_5,
            "pm10": pm10,
        },
        "profile": profile,
        "activity_level": activity_level,
        "category_description": cat["description"],
        "outdoor_recommendation": outdoor_rec,
        "tailored_precautions": precautions,
        "mask_recommendation": mask_rec,
        "disclaimer": DISCLAIMER_TEXT,
    }


def list_profiles() -> List[Dict[str, Any]]:
    """Return list of all supported profiles for UI rendering."""
    return list(PROFILES.values())
