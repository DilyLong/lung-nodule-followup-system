from __future__ import annotations

import json
import math
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import numpy as np
from sqlalchemy.orm import Session, joinedload

from ..models import Nodule, NoduleMeasurement, Patient
from ..settings import MODEL_ARTIFACT_DIR
from .features import calculate_temporal_features
from .model import FEATURE_VECTOR_NAMES, INPUT_SCHEMA_VERSION, build_temporal_model_input, feature_vector_from_input, validate_temporal_model_input

JSON_ARTIFACT = MODEL_ARTIFACT_DIR / "temporal_model.json"
TRAINING_REPORT = MODEL_ARTIFACT_DIR / "training_report.json"
TRAINING_DATA_SCHEMA_VERSION = "temporal-training-v1"

MALIGNANT_PATHOLOGY = {"AIS", "MIA", "浸润性腺癌", "鳞癌", "小细胞肺癌", "转移瘤", "恶性"}
BENIGN_PATHOLOGY = {"良性", "未手术"}
MALIGNANT_CLINICAL = {"恶性", "进展"}
BENIGN_CLINICAL = {"良性", "稳定", "缩小"}


@dataclass
class TrainingSample:
    patient_id: int
    patient_code: str
    nodule_id: int
    nodule_label: str
    label: int
    label_source: str
    model_input: dict[str, Any]
    features: np.ndarray


def label_from_nodule(nodule: Nodule) -> tuple[int | None, str | None]:
    pathology = (nodule.pathology_label or "").strip()
    clinical = (nodule.clinical_label or "").strip()
    if pathology in MALIGNANT_PATHOLOGY:
        return 1, "pathology_label"
    if pathology in BENIGN_PATHOLOGY and clinical in BENIGN_CLINICAL:
        return 0, "pathology_label+clinical_label"
    if clinical in MALIGNANT_CLINICAL:
        return 1, "clinical_label"
    if clinical in BENIGN_CLINICAL:
        return 0, "clinical_label"
    return None, None


def _measurement_payload(measurement: NoduleMeasurement) -> dict[str, Any]:
    study = measurement.study
    return {
        "study_id": study.id,
        "study_date": study.study_date,
        "diameter_mm": measurement.diameter_mm,
        "volume_mm3": measurement.volume_mm3,
        "mean_hu": measurement.mean_hu,
        "min_hu": measurement.min_hu,
        "max_hu": measurement.max_hu,
        "roi_area_mm2": measurement.roi_area_mm2,
        "solid_component_percent": measurement.solid_component_percent,
        "spiculation_score": measurement.spiculation_score,
        "lobulation_score": measurement.lobulation_score,
        "pleural_retraction_score": measurement.pleural_retraction_score,
    }


def collect_training_samples(db: Session) -> tuple[list[TrainingSample], list[dict[str, Any]]]:
    nodules = (
        db.query(Nodule)
        .join(Patient, Nodule.patient_id == Patient.id)
        .options(joinedload(Nodule.patient), joinedload(Nodule.measurements).joinedload(NoduleMeasurement.study))
        .order_by(Patient.patient_code, Nodule.id)
        .all()
    )
    samples: list[TrainingSample] = []
    exclusions: list[dict[str, Any]] = []
    for nodule in nodules:
        label, label_source = label_from_nodule(nodule)
        measurements = sorted([item for item in nodule.measurements if item.study], key=lambda item: item.study.study_date)
        reason = None
        if label is None:
            reason = "missing_binary_label"
        elif len(measurements) < 2:
            reason = "less_than_two_measurements"
        if reason:
            exclusions.append({"nodule_id": nodule.id, "patient_id": nodule.patient_id, "reason": reason})
            continue
        features = calculate_temporal_features([_measurement_payload(item) for item in measurements])
        model_input = build_temporal_model_input(features, nodule.nodule_type, nodule.patient.age, nodule.patient.smoking_history)
        issues = validate_temporal_model_input(model_input)
        if issues:
            exclusions.append({"nodule_id": nodule.id, "patient_id": nodule.patient_id, "reason": "schema_issues", "issues": issues})
            continue
        samples.append(
            TrainingSample(
                patient_id=nodule.patient_id,
                patient_code=nodule.patient.patient_code,
                nodule_id=nodule.id,
                nodule_label=nodule.label,
                label=int(label),
                label_source=label_source or "unknown",
                model_input=model_input,
                features=feature_vector_from_input(model_input).reshape(-1),
            )
        )
    return samples, exclusions


def training_readiness(db: Session) -> dict[str, Any]:
    samples, exclusions = collect_training_samples(db)
    positive = sum(item.label for item in samples)
    negative = len(samples) - positive
    has_report = TRAINING_REPORT.exists()
    report = _read_json(TRAINING_REPORT) if has_report else None
    return {
        "ready": len(samples) >= 4 and positive >= 1 and negative >= 1,
        "eligible_sample_count": len(samples),
        "positive_count": positive,
        "negative_count": negative,
        "excluded_count": len(exclusions),
        "exclusions": exclusions[:20],
        "artifact_path": str(JSON_ARTIFACT),
        "artifact_exists": JSON_ARTIFACT.exists(),
        "training_report_path": str(TRAINING_REPORT),
        "training_report_exists": has_report,
        "latest_report": report,
    }


def train_temporal_model(db: Session, operator: str = "系统") -> dict[str, Any]:
    samples, exclusions = collect_training_samples(db)
    positive = sum(item.label for item in samples)
    negative = len(samples) - positive
    if len(samples) < 4 or positive == 0 or negative == 0:
        return {
            "trained": False,
            "message": "至少需要 4 个带标签结节，且同时包含良性和恶性样本。",
            "operator": operator,
            "eligible_sample_count": len(samples),
            "positive_count": positive,
            "negative_count": negative,
            "excluded_count": len(exclusions),
            "exclusions": exclusions[:20],
        }

    x = np.vstack([item.features for item in samples]).astype(np.float64)
    y = np.asarray([item.label for item in samples], dtype=np.float64)
    train_idx, validation_idx = _split_indices(samples)
    x_train = x[train_idx]
    y_train = y[train_idx]
    x_val = x[validation_idx] if validation_idx.size else x[train_idx]
    y_val = y[validation_idx] if validation_idx.size else y[train_idx]

    mean = x_train.mean(axis=0)
    std = x_train.std(axis=0)
    std[std == 0] = 1.0
    x_train_scaled = (x_train - mean) / std
    x_val_scaled = (x_val - mean) / std
    weights, bias = _fit_logistic(x_train_scaled, y_train)
    val_prob = _sigmoid(x_val_scaled @ weights + bias)
    train_prob = _sigmoid(x_train_scaled @ weights + bias)
    thresholds = _risk_thresholds(train_prob, y_train)
    metrics = _classification_metrics(y_val, val_prob, thresholds)
    calibration = _calibration_bins(y_val, val_prob)
    generated_at = datetime.now(timezone.utc).isoformat()
    model_version = f"calibrated-tabular-{generated_at[:10]}-{len(samples)}"

    artifact = {
        "artifact_schema_version": "temporal-json-model-v1",
        "model_name": "Calibrated temporal tabular risk model",
        "model_version": model_version,
        "input_schema_version": INPUT_SCHEMA_VERSION,
        "training_data_schema_version": TRAINING_DATA_SCHEMA_VERSION,
        "generated_at": generated_at,
        "operator": operator,
        "feature_names": FEATURE_VECTOR_NAMES,
        "mean": mean.round(8).tolist(),
        "std": std.round(8).tolist(),
        "weights": weights.round(8).tolist(),
        "bias": round(float(bias), 8),
        "thresholds": thresholds,
    }
    MODEL_ARTIFACT_DIR.mkdir(parents=True, exist_ok=True)
    JSON_ARTIFACT.write_text(json.dumps(artifact, ensure_ascii=False, indent=2), encoding="utf-8")

    report = {
        "trained": True,
        "message": "模型训练、校准和验证完成。",
        "operator": operator,
        "generated_at": generated_at,
        "model_version": model_version,
        "artifact_path": str(JSON_ARTIFACT),
        "training_report_path": str(TRAINING_REPORT),
        "eligible_sample_count": len(samples),
        "positive_count": positive,
        "negative_count": negative,
        "excluded_count": len(exclusions),
        "train_sample_count": int(train_idx.size),
        "validation_sample_count": int(x_val.shape[0]),
        "metrics": metrics,
        "calibration_bins": calibration,
        "thresholds": thresholds,
        "feature_names": FEATURE_VECTOR_NAMES,
        "samples": [
            {
                "patient_id": item.patient_id,
                "patient_code": item.patient_code,
                "nodule_id": item.nodule_id,
                "nodule_label": item.nodule_label,
                "label": item.label,
                "label_source": item.label_source,
            }
            for item in samples
        ],
        "exclusions": exclusions[:50],
    }
    TRAINING_REPORT.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    return report


def _split_indices(samples: list[TrainingSample]) -> tuple[np.ndarray, np.ndarray]:
    positives = [index for index, item in enumerate(samples) if item.label == 1]
    negatives = [index for index, item in enumerate(samples) if item.label == 0]
    validation = []
    if len(positives) >= 2:
        validation.append(positives[-1])
    if len(negatives) >= 2:
        validation.append(negatives[-1])
    if not validation:
        validation = [len(samples) - 1]
    validation_set = set(validation)
    train = [index for index in range(len(samples)) if index not in validation_set]
    if len(set(samples[index].label for index in train)) < 2:
        train = list(range(len(samples)))
        validation = list(range(len(samples)))
    return np.asarray(train, dtype=int), np.asarray(validation, dtype=int)


def _fit_logistic(x: np.ndarray, y: np.ndarray) -> tuple[np.ndarray, float]:
    weights = np.zeros(x.shape[1], dtype=np.float64)
    bias = 0.0
    learning_rate = 0.08
    l2 = 0.02
    for _ in range(900):
        logits = x @ weights + bias
        prob = _sigmoid(logits)
        error = prob - y
        weights -= learning_rate * ((x.T @ error) / len(y) + l2 * weights)
        bias -= learning_rate * float(error.mean())
    return weights, bias


def _sigmoid(value: np.ndarray | float) -> np.ndarray:
    return 1.0 / (1.0 + np.exp(-np.clip(value, -30, 30)))


def _risk_thresholds(probabilities: np.ndarray, labels: np.ndarray) -> dict[str, float]:
    positive_probs = probabilities[labels == 1]
    negative_probs = probabilities[labels == 0]
    low = float(np.percentile(negative_probs, 75)) if negative_probs.size else 0.35
    high = float(np.percentile(positive_probs, 25)) if positive_probs.size else 0.65
    if high <= low:
        midpoint = (high + low) / 2
        low = max(0.2, midpoint - 0.1)
        high = min(0.8, midpoint + 0.1)
    return {"low_upper": round(low, 3), "high_lower": round(high, 3)}


def _classification_metrics(labels: np.ndarray, probabilities: np.ndarray, thresholds: dict[str, float]) -> dict[str, float]:
    cutoff = thresholds["high_lower"]
    predicted = (probabilities >= cutoff).astype(int)
    tp = int(np.sum((predicted == 1) & (labels == 1)))
    tn = int(np.sum((predicted == 0) & (labels == 0)))
    fp = int(np.sum((predicted == 1) & (labels == 0)))
    fn = int(np.sum((predicted == 0) & (labels == 1)))
    total = max(len(labels), 1)
    return {
        "auc": round(_auc(labels, probabilities), 3),
        "accuracy": round((tp + tn) / total, 3),
        "sensitivity": round(tp / max(tp + fn, 1), 3),
        "specificity": round(tn / max(tn + fp, 1), 3),
        "brier_score": round(float(np.mean((probabilities - labels) ** 2)), 3),
    }


def _auc(labels: np.ndarray, probabilities: np.ndarray) -> float:
    positives = probabilities[labels == 1]
    negatives = probabilities[labels == 0]
    if positives.size == 0 or negatives.size == 0:
        return 0.5
    wins = 0.0
    for pos in positives:
        wins += float(np.sum(pos > negatives)) + 0.5 * float(np.sum(pos == negatives))
    return wins / (positives.size * negatives.size)


def _calibration_bins(labels: np.ndarray, probabilities: np.ndarray) -> list[dict[str, Any]]:
    bins = []
    edges = np.linspace(0.0, 1.0, 6)
    for start, end in zip(edges[:-1], edges[1:]):
        mask = (probabilities >= start) & (probabilities < end if end < 1 else probabilities <= end)
        if not np.any(mask):
            continue
        bins.append(
            {
                "range": f"{start:.1f}-{end:.1f}",
                "count": int(np.sum(mask)),
                "mean_predicted": round(float(np.mean(probabilities[mask])), 3),
                "observed_rate": round(float(np.mean(labels[mask])), 3),
            }
        )
    return bins


def _read_json(path: Path) -> dict[str, Any] | None:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
