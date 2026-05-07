from datetime import date
from math import log
from typing import Any


def _days_between(first: date, last: date) -> int:
    return max((last - first).days, 1)


def calculate_temporal_features(measurements: list[dict[str, Any]]) -> dict[str, Any]:
    ordered = sorted(measurements, key=lambda item: item["study_date"])
    baseline = ordered[0]
    latest = ordered[-1]
    days = _days_between(baseline["study_date"], latest["study_date"])

    diameter_change = latest["diameter_mm"] - baseline["diameter_mm"]
    volume_change_percent = ((latest["volume_mm3"] - baseline["volume_mm3"]) / baseline["volume_mm3"]) * 100
    density_change = latest["mean_hu"] - baseline["mean_hu"]
    solid_component_change = latest["solid_component_percent"] - baseline["solid_component_percent"]

    vdt = None
    if latest["volume_mm3"] > baseline["volume_mm3"]:
        vdt = days * log(2) / log(latest["volume_mm3"] / baseline["volume_mm3"])

    annualized_diameter_growth = diameter_change / days * 365

    return {
        "timepoint_count": len(ordered),
        "followup_days": days,
        "diameter_change_mm": round(diameter_change, 2),
        "volume_change_percent": round(volume_change_percent, 2),
        "density_change_hu": round(density_change, 2),
        "solid_component_change_percent": round(solid_component_change, 2),
        "annualized_diameter_growth_mm": round(annualized_diameter_growth, 2),
        "volume_doubling_time_days": round(vdt, 1) if vdt else None,
        "spiculation_delta": round(latest["spiculation_score"] - baseline["spiculation_score"], 2),
        "lobulation_delta": round(latest["lobulation_score"] - baseline["lobulation_score"], 2),
        "pleural_retraction_delta": round(latest["pleural_retraction_score"] - baseline["pleural_retraction_score"], 2),
        "series": ordered,
    }
