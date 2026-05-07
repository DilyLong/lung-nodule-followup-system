from __future__ import annotations

import importlib.util
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import numpy as np

INPUT_SCHEMA_VERSION = "temporal-nodule-v1"
MODEL_VERSION = "surrogate-2026-05-07"
ARTIFACT_DIR = Path(__file__).resolve().parents[2] / "model_artifacts"
TORCH_ARTIFACT = ARTIFACT_DIR / "temporal_model.pt"
ONNX_ARTIFACT = ARTIFACT_DIR / "temporal_model.onnx"


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
    }


def _artifact_version(path: Path) -> str:
    return f"{path.stem}-{int(path.stat().st_mtime)}"


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
        }


def _surrogate_prediction(model_input: dict[str, Any], status: str, reason: str, artifact_path: Path | None = None) -> dict[str, Any]:
    result = TemporalSurrogateModel().predict(model_input)
    result["model_status"] = status
    result["fallback_reason"] = reason
    if artifact_path:
        result["model_artifact"] = artifact_path.name
    return result


def _artifact_model() -> tuple[Path, TemporalProgressionModel] | None:
    if TORCH_ARTIFACT.exists():
        return TORCH_ARTIFACT, TorchArtifactModel(TORCH_ARTIFACT)
    if ONNX_ARTIFACT.exists():
        return ONNX_ARTIFACT, OnnxArtifactModel(ONNX_ARTIFACT)
    return None


def _dependency_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def model_runtime_status() -> dict[str, Any]:
    torch_exists = TORCH_ARTIFACT.exists()
    onnx_exists = ONNX_ARTIFACT.exists()
    torch_available = _dependency_available("torch")
    onnxruntime_available = _dependency_available("onnxruntime")
    if torch_exists and torch_available:
        active_mode = "real_torch_ready"
        active_backend = "pytorch"
    elif onnx_exists and onnxruntime_available:
        active_mode = "real_onnx_ready"
        active_backend = "onnxruntime"
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
                "status": "ready" if torch_exists and torch_available else "missing_dependency" if torch_exists else "missing",
            },
            {
                "name": ONNX_ARTIFACT.name,
                "path": str(ONNX_ARTIFACT),
                "format": "ONNX .onnx",
                "exists": onnx_exists,
                "dependency": "onnxruntime",
                "dependency_available": onnxruntime_available,
                "status": "ready" if onnx_exists and onnxruntime_available else "missing_dependency" if onnx_exists else "missing",
            },
        ],
        "dependencies": {
            "torch": torch_available,
            "onnxruntime": onnxruntime_available,
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
        artifact_path = TORCH_ARTIFACT if TORCH_ARTIFACT.exists() else ONNX_ARTIFACT
        return _surrogate_prediction(model_input, "fallback_load_error", str(exc), artifact_path)

    if artifact_model is None:
        return _surrogate_prediction(model_input, "surrogate_no_weights", "No temporal_model.pt or temporal_model.onnx found in backend/model_artifacts")

    artifact_path, model = artifact_model
    try:
        return model.predict(model_input)
    except ModelSchemaError as exc:
        return _surrogate_prediction(model_input, "fallback_schema_mismatch", str(exc), artifact_path)
    except Exception as exc:
        return _surrogate_prediction(model_input, "fallback_inference_error", str(exc), artifact_path)
