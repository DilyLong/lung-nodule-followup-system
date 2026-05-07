from __future__ import annotations

import csv
import io
import json
import zipfile
from datetime import date, datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload

from .imports import DATASET_SPEC
from ..database import get_db
from ..models import AnalysisResult, Nodule, NoduleMeasurement, Patient, Study
from ..pipeline.model import model_runtime_status

router = APIRouter(prefix="/exports", tags=["exports"])

MEASUREMENT_FIELDS = [
    "measurement_id",
    "patient_id",
    "patient_code",
    "study_id",
    "study_date",
    "nodule_id",
    "nodule_label",
    "lobe",
    "nodule_type",
    "diameter_mm",
    "volume_mm3",
    "mean_hu",
    "min_hu",
    "max_hu",
    "roi_area_mm2",
    "solid_component_percent",
    "spiculation_score",
    "lobulation_score",
    "pleural_retraction_score",
    "thumbnail_seed",
]

COHORT_FIELDS = [
    "patient_id",
    "patient_code",
    "name",
    "sex",
    "age",
    "smoking_history",
    "family_history",
    "primary_diagnosis",
    "nodule_id",
    "nodule_label",
    "lobe",
    "nodule_type",
    "baseline_impression",
    "study_count",
    "measurement_count",
    "baseline_study_date",
    "latest_study_date",
    "baseline_diameter_mm",
    "latest_diameter_mm",
    "diameter_change_mm",
    "baseline_volume_mm3",
    "latest_volume_mm3",
    "volume_change_percent",
    "baseline_mean_hu",
    "latest_mean_hu",
    "density_change_hu",
    "baseline_solid_component_percent",
    "latest_solid_component_percent",
    "latest_risk_score",
    "latest_risk_level",
    "latest_analysis_at",
]


RESEARCH_FIELDS = [
    "analysis_id",
    "patient_id",
    "patient_code",
    "sex",
    "age",
    "smoking_history",
    "primary_diagnosis",
    "nodule_id",
    "nodule_label",
    "lobe",
    "nodule_type",
    "baseline_study_date",
    "latest_study_date",
    "timepoint_count",
    "followup_days",
    "baseline_diameter_mm",
    "latest_diameter_mm",
    "diameter_change_mm",
    "baseline_volume_mm3",
    "latest_volume_mm3",
    "volume_change_percent",
    "baseline_mean_hu",
    "latest_mean_hu",
    "density_change_hu",
    "baseline_solid_component_percent",
    "latest_solid_component_percent",
    "solid_component_change_percent",
    "annualized_diameter_growth_mm",
    "volume_doubling_time_days",
    "spiculation_delta",
    "lobulation_delta",
    "pleural_retraction_delta",
    "registration_quality",
    "risk_score",
    "risk_level",
    "recommendation",
    "model_name",
    "model_status",
    "model_version",
    "input_schema_version",
    "data_schema_version",
    "feature_version",
    "model_artifact",
    "model_artifact_hash",
    "model_input_feature_count",
    "inference_started_at",
    "analysis_generated_at",
    "backend",
    "top_contribution_1",
    "top_contribution_2",
    "top_contribution_3",
    "created_at",
]


def _csv_value(value: Any) -> Any:
    if value is None:
        return ""
    if isinstance(value, date | datetime):
        return value.isoformat()
    return value


def _csv_content(fields: list[str], rows: list[dict[str, Any]]) -> str:
    output = io.StringIO()
    output.write("﻿")
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: _csv_value(row.get(field)) for field in fields})
    return output.getvalue()


def _csv_response(filename: str, fields: list[str], rows: list[dict[str, Any]]) -> StreamingResponse:
    content = _csv_content(fields, rows)
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(iter([content]), media_type="text/csv; charset=utf-8", headers=headers)


def _parse_features(features_json: str) -> dict[str, Any]:
    try:
        parsed = json.loads(features_json)
    except json.JSONDecodeError:
        return {}
    return parsed if isinstance(parsed, dict) else {}


def _format_contribution(contributions: list[Any], index: int) -> str:
    if index >= len(contributions) or not isinstance(contributions[index], dict):
        return ""
    item = contributions[index]
    label = item.get("label", "-")
    value = item.get("value", "-")
    points = item.get("points", "-")
    return f"{label}:{value}:{points}"


def _ordered_measurements(nodule: Nodule) -> list[NoduleMeasurement]:
    return sorted(nodule.measurements, key=lambda measurement: measurement.study.study_date if measurement.study else date.min)


def _latest_analysis(patient: Patient, nodule: Nodule | None = None) -> AnalysisResult | None:
    analyses = list(patient.analyses)
    if nodule is not None:
        nodule_analyses = [analysis for analysis in analyses if analysis.nodule_id == nodule.id]
        if nodule_analyses:
            return max(nodule_analyses, key=lambda analysis: analysis.created_at)
        legacy = [analysis for analysis in analyses if analysis.nodule_id is None]
        if legacy:
            return max(legacy, key=lambda analysis: analysis.created_at)
        return None
    if not analyses:
        return None
    return max(analyses, key=lambda analysis: analysis.created_at)


def _percent_change(baseline: float | None, latest: float | None) -> float | None:
    if baseline is None or latest is None or baseline == 0:
        return None
    return round(((latest - baseline) / baseline) * 100, 3)


def _cohort_row(patient: Patient, nodule: Nodule | None) -> dict[str, Any]:
    latest_analysis = _latest_analysis(patient, nodule)
    if not nodule:
        baseline_study_date, latest_study_date = _study_dates(patient)
        return {
            "patient_id": patient.id,
            "patient_code": patient.patient_code,
            "name": patient.name,
            "sex": patient.sex,
            "age": patient.age,
            "smoking_history": patient.smoking_history,
            "family_history": patient.family_history,
            "primary_diagnosis": patient.primary_diagnosis,
            "study_count": len(patient.studies),
            "measurement_count": 0,
            "baseline_study_date": baseline_study_date,
            "latest_study_date": latest_study_date,
            "latest_risk_score": latest_analysis.risk_score if latest_analysis else None,
            "latest_risk_level": latest_analysis.risk_level if latest_analysis else None,
            "latest_analysis_at": latest_analysis.created_at if latest_analysis else None,
        }

    measurements = _ordered_measurements(nodule)
    baseline = measurements[0] if measurements else None
    latest = measurements[-1] if measurements else None
    return {
        "patient_id": patient.id,
        "patient_code": patient.patient_code,
        "name": patient.name,
        "sex": patient.sex,
        "age": patient.age,
        "smoking_history": patient.smoking_history,
        "family_history": patient.family_history,
        "primary_diagnosis": patient.primary_diagnosis,
        "nodule_id": nodule.id,
        "nodule_label": nodule.label,
        "lobe": nodule.lobe,
        "nodule_type": nodule.nodule_type,
        "baseline_impression": nodule.baseline_impression,
        "study_count": len(patient.studies),
        "measurement_count": len(measurements),
        "baseline_study_date": baseline.study.study_date if baseline else None,
        "latest_study_date": latest.study.study_date if latest else None,
        "baseline_diameter_mm": baseline.diameter_mm if baseline else None,
        "latest_diameter_mm": latest.diameter_mm if latest else None,
        "diameter_change_mm": round(latest.diameter_mm - baseline.diameter_mm, 3) if baseline and latest else None,
        "baseline_volume_mm3": baseline.volume_mm3 if baseline else None,
        "latest_volume_mm3": latest.volume_mm3 if latest else None,
        "volume_change_percent": _percent_change(baseline.volume_mm3 if baseline else None, latest.volume_mm3 if latest else None),
        "baseline_mean_hu": baseline.mean_hu if baseline else None,
        "latest_mean_hu": latest.mean_hu if latest else None,
        "density_change_hu": round(latest.mean_hu - baseline.mean_hu, 3) if baseline and latest else None,
        "baseline_solid_component_percent": baseline.solid_component_percent if baseline else None,
        "latest_solid_component_percent": latest.solid_component_percent if latest else None,
        "latest_risk_score": latest_analysis.risk_score if latest_analysis else None,
        "latest_risk_level": latest_analysis.risk_level if latest_analysis else None,
        "latest_analysis_at": latest_analysis.created_at if latest_analysis else None,
    }


def _first_nodule(patient: Patient) -> Nodule | None:
    if not patient.nodules:
        return None
    return sorted(patient.nodules, key=lambda item: item.id)[0]


def _study_dates(patient: Patient) -> tuple[Any, Any]:
    studies = sorted(patient.studies, key=lambda item: item.study_date)
    if not studies:
        return None, None
    return studies[0].study_date, studies[-1].study_date


def _build_measurement_rows(db: Session, patient_id: int | None = None) -> list[dict[str, Any]]:
    query = (
        db.query(NoduleMeasurement)
        .join(Nodule, NoduleMeasurement.nodule_id == Nodule.id)
        .join(Patient, Nodule.patient_id == Patient.id)
        .join(Study, NoduleMeasurement.study_id == Study.id)
        .options(joinedload(NoduleMeasurement.nodule).joinedload(Nodule.patient), joinedload(NoduleMeasurement.study))
        .order_by(Patient.patient_code, Study.study_date, Nodule.id, NoduleMeasurement.id)
    )
    if patient_id is not None:
        query = query.filter(Patient.id == patient_id)

    rows = []
    for measurement in query.all():
        nodule = measurement.nodule
        patient = nodule.patient
        study = measurement.study
        rows.append(
            {
                "measurement_id": measurement.id,
                "patient_id": patient.id,
                "patient_code": patient.patient_code,
                "study_id": study.id,
                "study_date": study.study_date,
                "nodule_id": nodule.id,
                "nodule_label": nodule.label,
                "lobe": nodule.lobe,
                "nodule_type": nodule.nodule_type,
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
                "thumbnail_seed": measurement.thumbnail_seed,
            }
        )
    return rows


@router.get("/measurements.csv")
def export_measurements(patient_id: int | None = Query(default=None), db: Session = Depends(get_db)) -> StreamingResponse:
    rows = _build_measurement_rows(db, patient_id)
    filename = f"patient-{patient_id}-measurements.csv" if patient_id else "measurements.csv"
    return _csv_response(filename, MEASUREMENT_FIELDS, rows)


def _nodule_from_analysis(patient: Patient, analysis: AnalysisResult, payload: dict[str, Any]) -> Nodule | None:
    if analysis.nodule_id is not None:
        for nodule in patient.nodules:
            if nodule.id == analysis.nodule_id:
                return nodule
    payload_nodule = payload.get("nodule") if isinstance(payload.get("nodule"), dict) else {}
    payload_nodule_id = payload_nodule.get("id")
    if payload_nodule_id is not None:
        for nodule in patient.nodules:
            if nodule.id == payload_nodule_id:
                return nodule
    return _first_nodule(patient)


def _build_research_rows(db: Session, patient_id: int | None = None) -> list[dict[str, Any]]:
    query = (
        db.query(AnalysisResult)
        .join(Patient, AnalysisResult.patient_id == Patient.id)
        .options(
            joinedload(AnalysisResult.patient).joinedload(Patient.studies),
            joinedload(AnalysisResult.patient).joinedload(Patient.nodules),
        )
        .order_by(Patient.patient_code, AnalysisResult.created_at)
    )
    if patient_id is not None:
        query = query.filter(Patient.id == patient_id)

    rows = []
    for analysis in query.all():
        patient = analysis.patient
        payload = _parse_features(analysis.features_json)
        nodule = _nodule_from_analysis(patient, analysis, payload)
        baseline_study_date, latest_study_date = _study_dates(patient)
        features = payload.get("features") if isinstance(payload.get("features"), dict) else {}
        risk = payload.get("risk") if isinstance(payload.get("risk"), dict) else {}
        trace = payload.get("trace") if isinstance(payload.get("trace"), dict) else {}
        registration = payload.get("registration") if isinstance(payload.get("registration"), dict) else {}
        series = features.get("series") if isinstance(features.get("series"), list) else []
        baseline = series[0] if series else {}
        latest = series[-1] if series else {}
        contributions = risk.get("contributions") if isinstance(risk.get("contributions"), list) else []

        rows.append(
            {
                "analysis_id": analysis.id,
                "patient_id": patient.id,
                "patient_code": patient.patient_code,
                "sex": patient.sex,
                "age": patient.age,
                "smoking_history": patient.smoking_history,
                "primary_diagnosis": patient.primary_diagnosis,
                "nodule_id": nodule.id if nodule else None,
                "nodule_label": nodule.label if nodule else None,
                "lobe": nodule.lobe if nodule else None,
                "nodule_type": nodule.nodule_type if nodule else risk.get("model_input", {}).get("clinical_features", {}).get("nodule_type"),
                "baseline_study_date": baseline.get("study_date", baseline_study_date),
                "latest_study_date": latest.get("study_date", latest_study_date),
                "timepoint_count": features.get("timepoint_count", risk.get("model_input", {}).get("timepoint_count")),
                "followup_days": features.get("followup_days"),
                "baseline_diameter_mm": baseline.get("diameter_mm"),
                "latest_diameter_mm": latest.get("diameter_mm"),
                "diameter_change_mm": features.get("diameter_change_mm", analysis.diameter_change_mm),
                "baseline_volume_mm3": baseline.get("volume_mm3"),
                "latest_volume_mm3": latest.get("volume_mm3"),
                "volume_change_percent": features.get("volume_change_percent", analysis.volume_change_percent),
                "baseline_mean_hu": baseline.get("mean_hu"),
                "latest_mean_hu": latest.get("mean_hu"),
                "density_change_hu": features.get("density_change_hu", analysis.density_change_hu),
                "baseline_solid_component_percent": baseline.get("solid_component_percent"),
                "latest_solid_component_percent": latest.get("solid_component_percent"),
                "solid_component_change_percent": features.get("solid_component_change_percent"),
                "annualized_diameter_growth_mm": features.get("annualized_diameter_growth_mm"),
                "volume_doubling_time_days": features.get("volume_doubling_time_days", analysis.volume_doubling_time_days),
                "spiculation_delta": features.get("spiculation_delta"),
                "lobulation_delta": features.get("lobulation_delta"),
                "pleural_retraction_delta": features.get("pleural_retraction_delta"),
                "registration_quality": registration.get("registration_quality", analysis.registration_quality),
                "risk_score": analysis.risk_score,
                "risk_level": analysis.risk_level,
                "recommendation": analysis.recommendation,
                "model_name": risk.get("model_name"),
                "model_status": risk.get("model_status"),
                "model_version": risk.get("model_version"),
                "input_schema_version": trace.get("input_schema_version", risk.get("input_schema_version")),
                "data_schema_version": trace.get("data_schema_version", risk.get("data_schema_version")),
                "feature_version": trace.get("feature_version", risk.get("feature_version")),
                "model_artifact": trace.get("model_artifact", risk.get("model_artifact")),
                "model_artifact_hash": trace.get("model_artifact_hash", risk.get("model_artifact_hash")),
                "model_input_feature_count": trace.get("model_input_feature_count", risk.get("model_input_feature_count")),
                "inference_started_at": trace.get("inference_started_at", risk.get("inference_started_at")),
                "analysis_generated_at": trace.get("analysis_generated_at"),
                "backend": trace.get("backend", risk.get("backend")),
                "top_contribution_1": _format_contribution(contributions, 0),
                "top_contribution_2": _format_contribution(contributions, 1),
                "top_contribution_3": _format_contribution(contributions, 2),
                "created_at": analysis.created_at,
            }
        )
    return rows


@router.get("/research-table.csv")
def export_research_table(patient_id: int | None = Query(default=None), db: Session = Depends(get_db)) -> StreamingResponse:
    rows = _build_research_rows(db, patient_id)
    filename = f"patient-{patient_id}-research-table.csv" if patient_id else "research-table.csv"
    return _csv_response(filename, RESEARCH_FIELDS, rows)


def _build_cohort_rows(db: Session, patient_id: int | None = None) -> list[dict[str, Any]]:
    query = (
        db.query(Patient)
        .options(
            joinedload(Patient.studies),
            joinedload(Patient.analyses),
            joinedload(Patient.nodules).joinedload(Nodule.measurements).joinedload(NoduleMeasurement.study),
        )
        .order_by(Patient.patient_code)
    )
    if patient_id is not None:
        query = query.filter(Patient.id == patient_id)

    rows = []
    for patient in query.all():
        if patient.nodules:
            for nodule in sorted(patient.nodules, key=lambda item: item.id):
                rows.append(_cohort_row(patient, nodule))
        else:
            rows.append(_cohort_row(patient, None))
    return rows


@router.get("/cohort-table.csv")
def export_cohort_table(patient_id: int | None = Query(default=None), db: Session = Depends(get_db)) -> StreamingResponse:
    rows = _build_cohort_rows(db, patient_id)
    filename = f"patient-{patient_id}-cohort-table.csv" if patient_id else "cohort-table.csv"
    return _csv_response(filename, COHORT_FIELDS, rows)


def _export_counts(db: Session, patient_id: int | None) -> dict[str, int]:
    patient_query = db.query(Patient)
    study_query = db.query(Study).join(Patient, Study.patient_id == Patient.id)
    nodule_query = db.query(Nodule).join(Patient, Nodule.patient_id == Patient.id)
    measurement_query = db.query(NoduleMeasurement).join(Nodule, NoduleMeasurement.nodule_id == Nodule.id).join(Patient, Nodule.patient_id == Patient.id)
    analysis_query = db.query(AnalysisResult).join(Patient, AnalysisResult.patient_id == Patient.id)
    if patient_id is not None:
        patient_query = patient_query.filter(Patient.id == patient_id)
        study_query = study_query.filter(Patient.id == patient_id)
        nodule_query = nodule_query.filter(Patient.id == patient_id)
        measurement_query = measurement_query.filter(Patient.id == patient_id)
        analysis_query = analysis_query.filter(Patient.id == patient_id)
    return {
        "patient_count": patient_query.count(),
        "study_count": study_query.count(),
        "nodule_count": nodule_query.count(),
        "measurement_count": measurement_query.count(),
        "analysis_count": analysis_query.count(),
    }


def _trace_field_names() -> list[str]:
    return [
        "data_schema_version",
        "feature_version",
        "input_schema_version",
        "model_version",
        "model_artifact",
        "model_artifact_hash",
        "model_input_feature_count",
        "inference_started_at",
        "analysis_generated_at",
    ]


def _package_metadata(db: Session, patient_id: int | None, cohort_rows: list[dict[str, Any]], measurement_rows: list[dict[str, Any]], research_rows: list[dict[str, Any]], model_status: dict[str, Any]) -> dict[str, Any]:
    counts = _export_counts(db, patient_id)
    return {
        "exported_at": datetime.now(timezone.utc).isoformat(),
        "scope": "patient" if patient_id is not None else "all",
        "patient_id": patient_id,
        "spec_version": DATASET_SPEC["spec_version"],
        "input_schema_version": model_status.get("input_schema_version"),
        "trace_fields": _trace_field_names(),
        "counts": counts,
        "row_counts": {
            "cohort_table": len(cohort_rows),
            "measurements": len(measurement_rows),
            "research_table": len(research_rows),
        },
        "files": [
            "cohort-table.csv",
            "measurements.csv",
            "research-table.csv",
            "imports-spec.json",
            "model-status.json",
            "metadata.json",
        ],
    }


@router.get("/research-package.zip")
def export_research_package(patient_id: int | None = Query(default=None), db: Session = Depends(get_db)) -> StreamingResponse:
    cohort_rows = _build_cohort_rows(db, patient_id)
    measurement_rows = _build_measurement_rows(db, patient_id)
    research_rows = _build_research_rows(db, patient_id)
    model_status = model_runtime_status()
    metadata = _package_metadata(db, patient_id, cohort_rows, measurement_rows, research_rows, model_status)

    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("cohort-table.csv", _csv_content(COHORT_FIELDS, cohort_rows))
        archive.writestr("measurements.csv", _csv_content(MEASUREMENT_FIELDS, measurement_rows))
        archive.writestr("research-table.csv", _csv_content(RESEARCH_FIELDS, research_rows))
        archive.writestr("imports-spec.json", json.dumps(DATASET_SPEC, ensure_ascii=False, indent=2, default=str))
        archive.writestr("model-status.json", json.dumps(model_status, ensure_ascii=False, indent=2, default=str))
        archive.writestr("metadata.json", json.dumps(metadata, ensure_ascii=False, indent=2, default=str))
    buffer.seek(0)

    filename = f"patient-{patient_id}-research-package.zip" if patient_id else "research-package.zip"
    headers = {"Content-Disposition": f'attachment; filename="{filename}"'}
    return StreamingResponse(buffer, media_type="application/zip", headers=headers)
