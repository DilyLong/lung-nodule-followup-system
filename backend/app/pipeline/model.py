from __future__ import annotations

from datetime import date, datetime, timezone
import hashlib
import importlib.util
import json
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import numpy as np

from ..settings import MODEL_ARTIFACT_DIR
from .features import calculate_temporal_features

INPUT_SCHEMA_VERSION = "temporal-nodule-v1"
FEATURE_VERSION = "temporal-features-v1"
DATA_SCHEMA_VERSION = "dataset-spec-v1"
MODEL_VERSION = "surrogate-2026-05-07"
ARTIFACT_DIR = MODEL_ARTIFACT_DIR
TORCH_ARTIFACT = ARTIFACT_DIR / "temporal_model.pt"
ONNX_ARTIFACT = ARTIFACT_DIR / "temporal_model.onnx"
JSON_ARTIFACT = ARTIFACT_DIR / "temporal_model.json"
TRAINING_REPORT = ARTIFACT_DIR / "training_report.json"
FEATURE_VECTOR_NAMES = [
    "timepoint_count",
    "age",
    "has_smoking_history",
    "nodule_type_pure_ground_glass",
    "nodule_type_part_solid",
    "nodule_type_solid",
    "followup_days",
    "diameter_change_mm",
    "volume_change_percent",
    "density_change_hu",
    "solid_component_change_percent",
    "annualized_diameter_growth_mm",
    "volume_doubling_time_days",
    "spiculation_delta",
    "lobulation_delta",
    "pleural_retraction_delta",
    "baseline_diameter_mm",
    "latest_diameter_mm",
    "baseline_volume_mm3",
    "latest_volume_mm3",
    "baseline_mean_hu",
    "latest_mean_hu",
    "baseline_solid_component_percent",
    "latest_solid_component_percent",
]


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


class ModelDependencyError(RuntimeError):
    pass


class ModelSchemaError(RuntimeError):
    pass


class ModelInferenceError(RuntimeError):
    pass


def _positive(value: float | None) -> float:
    return max(float(value or 0.0), 0.0)


def _has_smoking_history(smoking_history: str) -> bool:
    return "吸烟" in smoking_history and "无吸烟" not in smoking_history


def _risk_level(risk_score: float) -> str:
    if risk_score >= 0.68:
        return "高风险"
    if risk_score >= 0.38:
        return "中风险"
    return "低风险"


def _bounded_probability(value: float) -> float:
    if 0.0 <= value <= 1.0:
        return value
    return 1.0 / (1.0 + math.exp(-max(min(value, 20.0), -20.0)))


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


def _feature_vector(model_input: dict[str, Any]) -> np.ndarray:
    clinical = model_input.get("clinical_features", {})
    derived = model_input.get("derived_features", {})
    time_series = model_input.get("time_series", []) or []
    baseline = time_series[0] if time_series else {}
    latest = time_series[-1] if time_series else {}
    nodule_type = str(clinical.get("nodule_type") or "")
    values = [
        float(model_input.get("timepoint_count") or 0),
        float(clinical.get("age") or 0),
        1.0 if clinical.get("has_smoking_history") else 0.0,
        1.0 if "纯磨玻璃" in nodule_type else 0.0,
        1.0 if "部分实性" in nodule_type else 0.0,
        1.0 if nodule_type == "实性" else 0.0,
        float(derived.get("followup_days") or 0),
        float(derived.get("diameter_change_mm") or 0),
        float(derived.get("volume_change_percent") or 0),
        float(derived.get("density_change_hu") or 0),
        float(derived.get("solid_component_change_percent") or 0),
        float(derived.get("annualized_diameter_growth_mm") or 0),
        float(derived.get("volume_doubling_time_days") or 0),
        float(derived.get("spiculation_delta") or 0),
        float(derived.get("lobulation_delta") or 0),
        float(derived.get("pleural_retraction_delta") or 0),
        float(baseline.get("diameter_mm") or 0),
        float(latest.get("diameter_mm") or 0),
        float(baseline.get("volume_mm3") or 0),
        float(latest.get("volume_mm3") or 0),
        float(baseline.get("mean_hu") or 0),
        float(latest.get("mean_hu") or 0),
        float(baseline.get("solid_component_percent") or 0),
        float(latest.get("solid_component_percent") or 0),
    ]
    return np.asarray([values], dtype=np.float32)


def feature_vector_from_input(model_input: dict[str, Any]) -> np.ndarray:
    return _feature_vector(model_input)


def _reshape_for_onnx(features: np.ndarray, expected_shape: list[Any]) -> np.ndarray:
    if len(expected_shape) == 1:
        expected = expected_shape[0]
        vector = features.reshape(-1)
        if isinstance(expected, int) and expected > 0:
            vector = _pad_or_trim(vector, expected)
        return vector.astype(np.float32)
    if len(expected_shape) >= 2:
        expected = expected_shape[1]
        if isinstance(expected, int) and expected > 0:
            return _pad_or_trim(features.reshape(-1), expected).reshape(1, expected).astype(np.float32)
    return features.astype(np.float32)


def _pad_or_trim(vector: np.ndarray, length: int) -> np.ndarray:
    if vector.size == length:
        return vector
    if vector.size > length:
        return vector[:length]
    return np.pad(vector, (0, length - vector.size), mode="constant")


def _score_from_output(output: Any) -> float:
    if hasattr(output, "detach"):
        output = output.detach().cpu().numpy()
    if isinstance(output, list | tuple) and len(output) == 1:
        output = output[0]
    array = np.asarray(output, dtype=np.float32).reshape(-1)
    if array.size == 0:
        raise ModelSchemaError("model output is empty")
    if array.size == 1:
        return round(max(0.0, min(_bounded_probability(float(array[0])), 1.0)), 3)
    if np.all((array >= 0.0) & (array <= 1.0)) and float(np.sum(array)) <= 1.05:
        return round(max(0.0, min(float(array[-1]), 1.0)), 3)
    shifted = array - np.max(array)
    probabilities = np.exp(shifted) / np.sum(np.exp(shifted))
    return round(max(0.0, min(float(probabilities[-1]), 1.0)), 3)


def _normalize_model_output(output: Any, model_input: dict[str, Any], status: str, backend: str, artifact_path: Path) -> dict[str, Any]:
    if isinstance(output, dict):
        raw_score = output.get("risk_score", output.get("score"))
        if raw_score is None:
            raise ModelSchemaError("model output dict must include risk_score or score")
        risk_score = round(max(0.0, min(_bounded_probability(float(raw_score)), 1.0)), 3)
        contributions = output.get("contributions", [])
        if not isinstance(contributions, list):
            contributions = []
        return {
            "risk_score": risk_score,
            "risk_level": output.get("risk_level") or _risk_level(risk_score),
            "model_name": output.get("model_name") or "Temporal progression artifact model",
            "model_status": status,
            "model_version": output.get("model_version") or _artifact_version(artifact_path),
            "input_schema_version": INPUT_SCHEMA_VERSION,
            "backend": backend,
            "model_input": model_input,
            "contributions": contributions,
            "model_artifact": artifact_path.name,
            **_inference_metadata(model_input, artifact_path),
        }

    risk_score = _score_from_output(output)
    return {
        "risk_score": risk_score,
        "risk_level": _risk_level(risk_score),
        "model_name": "Temporal progression artifact model",
        "model_status": status,
        "model_version": _artifact_version(artifact_path),
        "input_schema_version": INPUT_SCHEMA_VERSION,
        "backend": backend,
        "model_input": model_input,
        "contributions": [],
        "model_artifact": artifact_path.name,
        **_inference_metadata(model_input, artifact_path),
    }


def _artifact_version(path: Path) -> str:
    return f"{path.stem}-{int(path.stat().st_mtime)}"


def _artifact_hash(path: Path | None) -> str | None:
    if not path or not path.exists():
        return None
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()[:16]


def _inference_metadata(model_input: dict[str, Any], artifact_path: Path | None = None) -> dict[str, Any]:
    return {
        "data_schema_version": DATA_SCHEMA_VERSION,
        "feature_version": FEATURE_VERSION,
        "input_schema_version": INPUT_SCHEMA_VERSION,
        "inference_started_at": datetime.now(timezone.utc).isoformat(),
        "model_artifact_hash": _artifact_hash(artifact_path),
        "model_artifact_path": str(artifact_path) if artifact_path else None,
        "model_input_feature_count": int(_feature_vector(model_input).shape[1]),
    }


def _json_model_contributions(features: np.ndarray, mean: np.ndarray, std: np.ndarray, weights: np.ndarray) -> list[dict[str, Any]]:
    scaled = (features - mean) / np.where(std == 0, 1.0, std)
    effects = scaled * weights
    ordered = sorted(zip(FEATURE_VECTOR_NAMES, features, effects, strict=True), key=lambda item: abs(float(item[2])), reverse=True)
    return [
        {"key": key, "label": key, "value": round(float(value), 3), "weight": round(float(effect), 4), "points": round(float(effect), 4)}
        for key, value, effect in ordered[:8]
    ]


class JsonArtifactModel:
    def __init__(self, artifact_path: Path):
        self.artifact_path = artifact_path
        try:
            self.artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ModelInferenceError("temporal_model.json cannot be read as a valid JSON artifact") from exc
        if self.artifact.get("input_schema_version") != INPUT_SCHEMA_VERSION:
            raise ModelSchemaError("JSON artifact input schema version mismatch")
        required = {"feature_names", "mean", "std", "weights", "bias", "thresholds"}
        missing = sorted(required - set(self.artifact))
        if missing:
            raise ModelSchemaError(f"JSON artifact missing fields: {', '.join(missing)}")
        if self.artifact["feature_names"] != FEATURE_VECTOR_NAMES:
            raise ModelSchemaError("JSON artifact feature names do not match current feature vector")

    def predict(self, model_input: dict[str, Any]) -> dict[str, Any]:
        if model_input.get("input_schema_version") != INPUT_SCHEMA_VERSION:
            raise ModelSchemaError("input schema version mismatch")
        features = _feature_vector(model_input).reshape(-1).astype(np.float64)
        mean = np.asarray(self.artifact["mean"], dtype=np.float64)
        std = np.asarray(self.artifact["std"], dtype=np.float64)
        weights = np.asarray(self.artifact["weights"], dtype=np.float64)
        if features.shape != mean.shape or features.shape != std.shape or features.shape != weights.shape:
            raise ModelSchemaError("JSON artifact feature vector length mismatch")
        std = np.where(std == 0, 1.0, std)
        risk_score = round(float(_bounded_probability(float(((features - mean) / std) @ weights + float(self.artifact["bias"])))), 3)
        thresholds = self.artifact.get("thresholds", {})
        high = float(thresholds.get("high_lower", 0.68))
        low = float(thresholds.get("low_upper", 0.38))
        if risk_score >= high:
            risk_level = "高风险"
        elif risk_score >= low:
            risk_level = "中风险"
        else:
            risk_level = "低风险"
        return _normalize_model_output(
            {
                "risk_score": risk_score,
                "risk_level": risk_level,
                "model_name": self.artifact.get("model_name", "Calibrated temporal tabular risk model"),
                "model_version": self.artifact.get("model_version"),
                "contributions": _json_model_contributions(features, mean, std, weights),
            },
            model_input,
            "real_json_loaded",
            "json_logistic_regression",
            self.artifact_path,
        )


class TorchArtifactModel:
    def __init__(self, artifact_path: Path):
        try:
            import torch
        except ImportError as exc:
            raise ModelDependencyError("torch is not installed; install backend/requirements-optional.txt to enable .pt inference") from exc

        self.torch = torch
        self.artifact_path = artifact_path
        try:
            self.model = torch.jit.load(str(artifact_path), map_location="cpu")
        except Exception as exc:
            raise ModelInferenceError(".pt artifact must be a TorchScript model for safe local inference") from exc
        if hasattr(self.model, "eval"):
            self.model.eval()

    def predict(self, model_input: dict[str, Any]) -> dict[str, Any]:
        if model_input.get("input_schema_version") != INPUT_SCHEMA_VERSION:
            raise ModelSchemaError("input schema version mismatch")
        with self.torch.no_grad():
            candidate = self.model
            if isinstance(candidate, dict):
                candidate = candidate.get("predict") or candidate.get("model")
            if hasattr(candidate, "predict"):
                output = candidate.predict(model_input)
            elif callable(candidate):
                tensor = self.torch.tensor(_feature_vector(model_input), dtype=self.torch.float32)
                output = candidate(tensor)
            else:
                raise ModelSchemaError(".pt artifact must be callable or expose predict(model_input)")
        return _normalize_model_output(output, model_input, "real_torch_loaded", "pytorch", self.artifact_path)


class OnnxArtifactModel:
    def __init__(self, artifact_path: Path):
        try:
            import onnxruntime as ort
        except ImportError as exc:
            raise ModelDependencyError("onnxruntime is not installed; install it to enable .onnx inference") from exc

        self.artifact_path = artifact_path
        try:
            self.session = ort.InferenceSession(str(artifact_path), providers=["CPUExecutionProvider"])
        except Exception as exc:
            raise ModelInferenceError(str(exc)) from exc

    def predict(self, model_input: dict[str, Any]) -> dict[str, Any]:
        if model_input.get("input_schema_version") != INPUT_SCHEMA_VERSION:
            raise ModelSchemaError("input schema version mismatch")
        inputs = self.session.get_inputs()
        if not inputs:
            raise ModelSchemaError("ONNX model has no input tensor")
        first_input = inputs[0]
        features = _reshape_for_onnx(_feature_vector(model_input), list(first_input.shape))
        output = self.session.run(None, {first_input.name: features})
        return _normalize_model_output(output, model_input, "real_onnx_loaded", "onnxruntime", self.artifact_path)


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
        ordered = sorted(contributions, key=lambda item: item.points, reverse=True)
        return {
            "risk_score": risk_score,
            "risk_level": _risk_level(risk_score),
            "model_name": self.model_name,
            "model_status": "surrogate_no_weights",
            "model_version": MODEL_VERSION,
            "input_schema_version": INPUT_SCHEMA_VERSION,
            "backend": self.backend,
            "model_input": model_input,
            "contributions": [item.as_dict() for item in ordered],
            **_inference_metadata(model_input),
        }


def _surrogate_prediction(model_input: dict[str, Any], status: str, reason: str, artifact_path: Path | None = None) -> dict[str, Any]:
    result = TemporalSurrogateModel().predict(model_input)
    result["model_status"] = status
    result["fallback_reason"] = reason
    if artifact_path:
        result["model_artifact"] = artifact_path.name
    return result


def validate_temporal_model_input(model_input: dict[str, Any]) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []

    def add_issue(field: str, message: str) -> None:
        issues.append({"field": field, "severity": "error", "message": message})

    if model_input.get("input_schema_version") != INPUT_SCHEMA_VERSION:
        add_issue("input_schema_version", f"Expected {INPUT_SCHEMA_VERSION}")

    timepoint_count = model_input.get("timepoint_count")
    if not isinstance(timepoint_count, int) or timepoint_count < 2:
        add_issue("timepoint_count", "At least two temporal points are required")

    time_series = model_input.get("time_series")
    if not isinstance(time_series, list) or len(time_series) < 2:
        add_issue("time_series", "time_series must include at least two points")
    else:
        if isinstance(timepoint_count, int) and timepoint_count != len(time_series):
            add_issue("timepoint_count", "timepoint_count must match time_series length")
        required_numeric = [
            "diameter_mm",
            "volume_mm3",
            "mean_hu",
            "solid_component_percent",
            "spiculation_score",
            "lobulation_score",
            "pleural_retraction_score",
        ]
        previous_date = ""
        for index, point in enumerate(time_series):
            if not isinstance(point, dict):
                add_issue(f"time_series[{index}]", "Each time point must be an object")
                continue
            if point.get("study_id") is None:
                add_issue(f"time_series[{index}].study_id", "study_id is required")
            study_date = point.get("study_date")
            if not study_date:
                add_issue(f"time_series[{index}].study_date", "study_date is required")
            elif previous_date and str(study_date) < previous_date:
                add_issue(f"time_series[{index}].study_date", "study_date must be chronological")
            previous_date = str(study_date or previous_date)
            for key in required_numeric:
                value = point.get(key)
                if not isinstance(value, int | float):
                    add_issue(f"time_series[{index}].{key}", f"{key} must be numeric")
                elif key in {"diameter_mm", "volume_mm3"} and value <= 0:
                    add_issue(f"time_series[{index}].{key}", f"{key} must be positive")

    clinical = model_input.get("clinical_features")
    if not isinstance(clinical, dict):
        add_issue("clinical_features", "clinical_features is required")
    else:
        age = clinical.get("age")
        if not isinstance(age, int | float) or age <= 0:
            add_issue("clinical_features.age", "age must be positive")
        if not clinical.get("nodule_type"):
            add_issue("clinical_features.nodule_type", "nodule_type is required")
        if "has_smoking_history" not in clinical:
            add_issue("clinical_features.has_smoking_history", "has_smoking_history is required")

    derived = model_input.get("derived_features")
    if not isinstance(derived, dict):
        add_issue("derived_features", "derived_features is required")
    else:
        required_derived = [
            "followup_days",
            "diameter_change_mm",
            "volume_change_percent",
            "density_change_hu",
            "solid_component_change_percent",
            "annualized_diameter_growth_mm",
            "spiculation_delta",
            "lobulation_delta",
            "pleural_retraction_delta",
        ]
        for key in required_derived:
            if key not in derived:
                add_issue(f"derived_features.{key}", f"{key} is required")
            elif derived[key] is not None and not isinstance(derived[key], int | float):
                add_issue(f"derived_features.{key}", f"{key} must be numeric or null")

    return issues


def build_demo_self_check_input() -> dict[str, Any]:
    measurements = [
        {
            "study_id": 9001,
            "study_date": date(2024, 1, 8),
            "diameter_mm": 7.4,
            "volume_mm3": 218.0,
            "mean_hu": -612.0,
            "min_hu": -820.0,
            "max_hu": -168.0,
            "roi_area_mm2": 42.0,
            "solid_component_percent": 18.0,
            "spiculation_score": 0.18,
            "lobulation_score": 0.12,
            "pleural_retraction_score": 0.05,
        },
        {
            "study_id": 9002,
            "study_date": date(2024, 7, 12),
            "diameter_mm": 8.5,
            "volume_mm3": 306.0,
            "mean_hu": -548.0,
            "min_hu": -760.0,
            "max_hu": -92.0,
            "roi_area_mm2": 53.0,
            "solid_component_percent": 26.0,
            "spiculation_score": 0.24,
            "lobulation_score": 0.18,
            "pleural_retraction_score": 0.09,
        },
        {
            "study_id": 9003,
            "study_date": date(2025, 1, 16),
            "diameter_mm": 9.8,
            "volume_mm3": 452.0,
            "mean_hu": -486.0,
            "min_hu": -702.0,
            "max_hu": -38.0,
            "roi_area_mm2": 68.0,
            "solid_component_percent": 38.0,
            "spiculation_score": 0.35,
            "lobulation_score": 0.26,
            "pleural_retraction_score": 0.16,
        },
    ]
    features = calculate_temporal_features(measurements)
    return build_temporal_model_input(features, "部分实性", 64, "既往吸烟 30 包年，已戒烟")


def _self_check_passes(mode: str, schema_issues: list[dict[str, Any]], inference: dict[str, Any] | None) -> bool:
    if schema_issues or inference is None:
        return False
    model_status = inference.get("model_status")
    if model_status in {"fallback_load_error", "fallback_schema_mismatch", "fallback_inference_error"}:
        return False
    if mode == "fallback_missing_dependency":
        return False
    return True


def _model_input_preview(model_input: dict[str, Any]) -> dict[str, Any]:
    return {
        "input_schema_version": model_input.get("input_schema_version"),
        "timepoint_count": model_input.get("timepoint_count"),
        "time_series": model_input.get("time_series", [])[:3],
        "clinical_features": model_input.get("clinical_features"),
        "derived_features": model_input.get("derived_features"),
    }


def _output_contract_issues(inference: dict[str, Any] | None, expected_feature_count: int) -> list[dict[str, Any]]:
    issues: list[dict[str, Any]] = []
    if inference is None:
        return [{"field": "inference", "severity": "error", "message": "Inference output is missing"}]
    score = inference.get("risk_score")
    if not isinstance(score, int | float) or not 0 <= float(score) <= 1:
        issues.append({"field": "risk_score", "severity": "error", "message": "risk_score must be a 0-1 number"})
    if inference.get("risk_level") not in {"低风险", "中风险", "高风险"}:
        issues.append({"field": "risk_level", "severity": "error", "message": "risk_level must be 低风险/中风险/高风险"})
    for field in ["model_status", "model_version", "backend"]:
        if not inference.get(field):
            issues.append({"field": field, "severity": "error", "message": f"{field} is required"})
    feature_count = inference.get("model_input_feature_count")
    if feature_count != expected_feature_count:
        issues.append({"field": "model_input_feature_count", "severity": "error", "message": f"Expected {expected_feature_count}, got {feature_count}"})
    return issues


def run_model_self_check() -> dict[str, Any]:
    runtime_status = model_runtime_status()
    model_input = build_demo_self_check_input()
    schema_issues = validate_temporal_model_input(model_input)
    checks = [
        {
            "name": "artifact_status",
            "passed": runtime_status["active_mode"] != "fallback_missing_dependency",
            "message": active_mode_message(runtime_status["active_mode"]),
        },
        {
            "name": "input_schema",
            "passed": not schema_issues,
            "message": "Demo input matches temporal-nodule-v1" if not schema_issues else f"{len(schema_issues)} schema issue(s) found",
        },
    ]
    issues = list(schema_issues)
    inference: dict[str, Any] | None = None
    expected_feature_count = int(_feature_vector(model_input).shape[1])
    if not schema_issues:
        try:
            inference = predict_progression_risk(
                {"series": model_input["time_series"], **model_input["derived_features"], "timepoint_count": model_input["timepoint_count"]},
                model_input["clinical_features"]["nodule_type"],
                int(model_input["clinical_features"]["age"]),
                model_input["clinical_features"]["smoking_history"],
            )
            inference.pop("model_input", None)
            inference_status = inference.get("model_status")
            inference_passed = inference_status not in {"fallback_load_error", "fallback_schema_mismatch", "fallback_inference_error"}
            checks.append(
                {
                    "name": "inference",
                    "passed": inference_passed,
                    "message": "Dry-run inference completed" if inference_passed else f"Dry-run fell back because of {inference_status}",
                }
            )
            if inference_status == "fallback_missing_dependency":
                issues.append({"field": "model_artifact", "severity": "warning", "message": inference.get("fallback_reason", "Model dependency is missing")})
            elif inference_status in {"fallback_load_error", "fallback_schema_mismatch", "fallback_inference_error"}:
                issues.append({"field": "model_artifact", "severity": "error", "message": inference.get("fallback_reason", "Real model dry-run failed")})
            elif inference_status == "surrogate_no_weights":
                issues.append({"field": "model_artifact", "severity": "warning", "message": "No real model weights found; surrogate dry-run passed"})
            elif inference_status == "real_json_loaded":
                issues.append({"field": "model_artifact", "severity": "warning", "message": "JSON model is trained in-app from current cohort labels; validate externally before clinical use"})
            output_issues = _output_contract_issues(inference, expected_feature_count)
            checks.append(
                {
                    "name": "output_contract",
                    "passed": not output_issues,
                    "message": "Risk output contract is valid" if not output_issues else f"{len(output_issues)} output contract issue(s) found",
                }
            )
            issues.extend(output_issues)
        except Exception as exc:
            checks.append({"name": "inference", "passed": False, "message": str(exc)})
            issues.append({"field": "inference", "severity": "error", "message": str(exc)})

    passed = _self_check_passes(runtime_status["active_mode"], schema_issues, inference) and all(check["passed"] for check in checks)
    return {
        "passed": passed,
        "mode": runtime_status["active_mode"],
        "backend": runtime_status["active_backend"],
        "demo_input_source": "synthetic_temporal_fixture",
        "checks": checks,
        "issues": issues,
        "model_input_preview": _model_input_preview(model_input),
        "inference": inference,
        "runtime_status": runtime_status,
    }


def active_mode_message(mode: str) -> str:
    messages = {
        "real_torch_ready": "TorchScript artifact and torch dependency are available",
        "real_onnx_ready": "ONNX artifact and onnxruntime dependency are available",
        "real_json_ready": "JSON calibrated temporal model artifact is available",
        "surrogate_no_weights": "No real artifact found; surrogate backend will be checked",
        "fallback_missing_dependency": "A real artifact exists but its runtime dependency is missing",
    }
    return messages.get(mode, mode)


def _artifact_model() -> tuple[Path, TemporalProgressionModel] | None:
    if TORCH_ARTIFACT.exists():
        return TORCH_ARTIFACT, TorchArtifactModel(TORCH_ARTIFACT)
    if ONNX_ARTIFACT.exists():
        return ONNX_ARTIFACT, OnnxArtifactModel(ONNX_ARTIFACT)
    if JSON_ARTIFACT.exists():
        return JSON_ARTIFACT, JsonArtifactModel(JSON_ARTIFACT)
    return None


def _dependency_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def model_runtime_status() -> dict[str, Any]:
    torch_exists = TORCH_ARTIFACT.exists()
    onnx_exists = ONNX_ARTIFACT.exists()
    json_exists = JSON_ARTIFACT.exists()
    training_report_exists = TRAINING_REPORT.exists()
    torch_available = _dependency_available("torch")
    onnxruntime_available = _dependency_available("onnxruntime")
    if torch_exists and torch_available:
        active_mode = "real_torch_ready"
        active_backend = "pytorch"
    elif onnx_exists and onnxruntime_available:
        active_mode = "real_onnx_ready"
        active_backend = "onnxruntime"
    elif json_exists:
        active_mode = "real_json_ready"
        active_backend = "json_logistic_regression"
    elif torch_exists and not torch_available:
        active_mode = "fallback_missing_dependency"
        active_backend = "deterministic_surrogate"
    elif onnx_exists and not onnxruntime_available:
        active_mode = "fallback_missing_dependency"
        active_backend = "deterministic_surrogate"
    else:
        active_mode = "surrogate_no_weights"
        active_backend = "deterministic_surrogate"

    return {
        "artifact_dir": str(ARTIFACT_DIR),
        "input_schema_version": INPUT_SCHEMA_VERSION,
        "surrogate_model_version": MODEL_VERSION,
        "active_mode": active_mode,
        "active_backend": active_backend,
        "artifacts": [
            {
                "name": TORCH_ARTIFACT.name,
                "path": str(TORCH_ARTIFACT),
                "format": "TorchScript .pt",
                "exists": torch_exists,
                "dependency": "torch",
                "dependency_available": torch_available,
                "sha256": _artifact_hash(TORCH_ARTIFACT),
                "status": "ready" if torch_exists and torch_available else "missing_dependency" if torch_exists else "missing",
            },
            {
                "name": ONNX_ARTIFACT.name,
                "path": str(ONNX_ARTIFACT),
                "format": "ONNX .onnx",
                "exists": onnx_exists,
                "dependency": "onnxruntime",
                "dependency_available": onnxruntime_available,
                "sha256": _artifact_hash(ONNX_ARTIFACT),
                "status": "ready" if onnx_exists and onnxruntime_available else "missing_dependency" if onnx_exists else "missing",
            },
            {
                "name": JSON_ARTIFACT.name,
                "path": str(JSON_ARTIFACT),
                "format": "Calibrated JSON",
                "exists": json_exists,
                "dependency": "numpy",
                "dependency_available": True,
                "sha256": _artifact_hash(JSON_ARTIFACT),
                "status": "ready" if json_exists else "missing",
            },
            {
                "name": TRAINING_REPORT.name,
                "path": str(TRAINING_REPORT),
                "format": "Training report JSON",
                "exists": training_report_exists,
                "dependency": "none",
                "dependency_available": True,
                "sha256": _artifact_hash(TRAINING_REPORT),
                "status": "ready" if training_report_exists else "missing",
            },
        ],
        "dependencies": {
            "torch": torch_available,
            "onnxruntime": onnxruntime_available,
            "numpy": True,
        },
        "fallback_model": {
            "name": TemporalSurrogateModel.model_name,
            "backend": TemporalSurrogateModel.backend,
            "status": "available",
        },
    }
def predict_progression_risk(features: dict[str, Any], nodule_type: str, age: int, smoking_history: str) -> dict[str, Any]:
    model_input = build_temporal_model_input(features, nodule_type, age, smoking_history)
    try:
        artifact_model = _artifact_model()
    except ModelDependencyError as exc:
        artifact_path = TORCH_ARTIFACT if TORCH_ARTIFACT.exists() else ONNX_ARTIFACT
        return _surrogate_prediction(model_input, "fallback_missing_dependency", str(exc), artifact_path)
    except ModelInferenceError as exc:
        artifact_path = TORCH_ARTIFACT if TORCH_ARTIFACT.exists() else ONNX_ARTIFACT if ONNX_ARTIFACT.exists() else JSON_ARTIFACT
        return _surrogate_prediction(model_input, "fallback_load_error", str(exc), artifact_path)
    except ModelSchemaError as exc:
        artifact_path = TORCH_ARTIFACT if TORCH_ARTIFACT.exists() else ONNX_ARTIFACT if ONNX_ARTIFACT.exists() else JSON_ARTIFACT
        return _surrogate_prediction(model_input, "fallback_schema_mismatch", str(exc), artifact_path)

    if artifact_model is None:
        return _surrogate_prediction(model_input, "surrogate_no_weights", "No temporal_model.pt, temporal_model.onnx, or temporal_model.json found in backend/model_artifacts")

    artifact_path, model = artifact_model
    try:
        return model.predict(model_input)
    except ModelSchemaError as exc:
        return _surrogate_prediction(model_input, "fallback_schema_mismatch", str(exc), artifact_path)
    except Exception as exc:
        return _surrogate_prediction(model_input, "fallback_inference_error", str(exc), artifact_path)
