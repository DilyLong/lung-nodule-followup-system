from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Protocol

INPUT_SCHEMA_VERSION = "temporal-nodule-v1"
MODEL_VERSION = "surrogate-2026-05-07"


@dataclass
class Contribution:
    key: str
    label: str
    value: str
    weight: float
    points: float

    def as_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "label": self.label,
            "value": self.value,
            "weight": self.weight,
            "points": round(self.points, 3),
        }


class TemporalProgressionModel(Protocol):
    def predict(self, model_input: dict[str, Any]) -> dict[str, Any]:
        ...


def _positive(value: float | None) -> float:
    return max(float(value or 0.0), 0.0)


def _has_smoking_history(smoking_history: str) -> bool:
    return "吸烟" in smoking_history and "无吸烟" not in smoking_history


def build_temporal_model_input(features: dict[str, Any], nodule_type: str, age: int, smoking_history: str) -> dict[str, Any]:
    time_series = [
        {
            "study_id": item["study_id"],
            "study_date": item["study_date"],
            "diameter_mm": item["diameter_mm"],
            "volume_mm3": item["volume_mm3"],
            "mean_hu": item["mean_hu"],
            "min_hu": item.get("min_hu"),
            "max_hu": item.get("max_hu"),
            "roi_area_mm2": item.get("roi_area_mm2"),
            "solid_component_percent": item["solid_component_percent"],
            "spiculation_score": item["spiculation_score"],
            "lobulation_score": item["lobulation_score"],
            "pleural_retraction_score": item["pleural_retraction_score"],
        }
        for item in features.get("series", [])
    ]
    return {
        "input_schema_version": INPUT_SCHEMA_VERSION,
        "timepoint_count": features.get("timepoint_count", len(time_series)),
        "time_series": time_series,
        "clinical_features": {
            "age": age,
            "smoking_history": smoking_history,
            "has_smoking_history": _has_smoking_history(smoking_history),
            "nodule_type": nodule_type,
        },
        "derived_features": {
            "followup_days": features.get("followup_days"),
            "diameter_change_mm": features.get("diameter_change_mm"),
            "volume_change_percent": features.get("volume_change_percent"),
            "density_change_hu": features.get("density_change_hu"),
            "solid_component_change_percent": features.get("solid_component_change_percent"),
            "annualized_diameter_growth_mm": features.get("annualized_diameter_growth_mm"),
            "volume_doubling_time_days": features.get("volume_doubling_time_days"),
            "spiculation_delta": features.get("spiculation_delta"),
            "lobulation_delta": features.get("lobulation_delta"),
            "pleural_retraction_delta": features.get("pleural_retraction_delta"),
        },
    }


class TemporalSurrogateModel:
    model_name = "ConvLSTM-compatible temporal surrogate"
    backend = "deterministic_surrogate"

    def _contributions(self, model_input: dict[str, Any]) -> list[Contribution]:
        derived = model_input["derived_features"]
        clinical = model_input["clinical_features"]
        vdt = derived.get("volume_doubling_time_days")
        morphology_delta = _positive(derived.get("spiculation_delta")) + _positive(derived.get("lobulation_delta")) + _positive(derived.get("pleural_retraction_delta"))
        contributions = [
            Contribution("diameter_growth", "最大径增长", f"{derived.get('diameter_change_mm') or 0:.1f} mm", 0.08, _positive(derived.get("diameter_change_mm")) * 0.08),
            Contribution("volume_growth", "体积增长", f"{derived.get('volume_change_percent') or 0:.1f}%", 0.003, _positive(derived.get("volume_change_percent")) * 0.003),
            Contribution("solid_component", "实性成分增加", f"{derived.get('solid_component_change_percent') or 0:.1f}%", 0.012, _positive(derived.get("solid_component_change_percent")) * 0.012),
            Contribution("density_change", "密度升高", f"{derived.get('density_change_hu') or 0:.1f} HU", 0.002, _positive(derived.get("density_change_hu")) * 0.002),
            Contribution("morphology", "形态恶性征变化", f"{morphology_delta:.2f}", 0.08, morphology_delta * 0.08),
            Contribution("solid_type", "实性/混合类型", clinical["nodule_type"], 0.08, 0.08 if "实性" in clinical["nodule_type"] else 0.0),
            Contribution("age", "年龄", f"{clinical['age']} 岁", 0.05, 0.05 if clinical["age"] >= 60 else 0.0),
            Contribution("smoking", "吸烟史", clinical["smoking_history"], 0.06, 0.06 if clinical["has_smoking_history"] else 0.0),
        ]
        if vdt and vdt < 500:
            contributions.append(Contribution("vdt", "体积倍增时间", f"{vdt} 天", 0.14, 0.14))
        elif vdt and vdt < 900:
            contributions.append(Contribution("vdt", "体积倍增时间", f"{vdt} 天", 0.07, 0.07))
        return contributions

    def predict(self, model_input: dict[str, Any]) -> dict[str, Any]:
        contributions = self._contributions(model_input)
        score = 0.18 + sum(item.points for item in contributions)
        risk_score = round(max(0.02, min(score, 0.96)), 3)
        if risk_score >= 0.68:
            level = "高风险"
        elif risk_score >= 0.38:
            level = "中风险"
        else:
            level = "低风险"
        ordered = sorted(contributions, key=lambda item: item.points, reverse=True)
        return {
            "risk_score": risk_score,
            "risk_level": level,
            "model_name": self.model_name,
            "model_status": "surrogate_no_weights",
            "model_version": MODEL_VERSION,
            "input_schema_version": INPUT_SCHEMA_VERSION,
            "backend": self.backend,
            "model_input": model_input,
            "contributions": [item.as_dict() for item in ordered],
        }


def predict_progression_risk(features: dict[str, Any], nodule_type: str, age: int, smoking_history: str) -> dict[str, Any]:
    model_input = build_temporal_model_input(features, nodule_type, age, smoking_history)
    return TemporalSurrogateModel().predict(model_input)
