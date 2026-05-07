from __future__ import annotations

import csv
import io
import json
from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models import AnalysisResult, Nodule, NoduleMeasurement, Patient, Study

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


def _csv_response(filename: str, fields: list[str], rows: list[dict[str, Any]]) -> StreamingResponse:
    output = io.StringIO()
    output.write("﻿")
    writer = csv.DictWriter(output, fieldnames=fields, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({field: _csv_value(row.get(field)) for field in fields})
    content = output.getvalue()
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


def _first_nodule(patient: Patient) -> Nodule | None:
    if not patient.nodules:
        return None
    return sorted(patient.nodules, key=lambda item: item.id)[0]


def _study_dates(patient: Patient) -> tuple[Any, Any]:
    studies = sorted(patient.studies, key=lambda item: item.study_date)
    if not studies:
        return None, None
    return studies[0].study_date, studies[-1].study_date


@router.get("/measurements.csv")
def export_measurements(patient_id: int | None = Query(default=None), db: Session = Depends(get_db)) -> StreamingResponse:
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

    filename = f"patient-{patient_id}-measurements.csv" if patient_id else "measurements.csv"
    return _csv_response(filename, MEASUREMENT_FIELDS, rows)


@router.get("/research-table.csv")
def export_research_table(patient_id: int | None = Query(default=None), db: Session = Depends(get_db)) -> StreamingResponse:
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
        nodule = _first_nodule(patient)
        baseline_study_date, latest_study_date = _study_dates(patient)
        payload = _parse_features(analysis.features_json)
        features = payload.get("features") if isinstance(payload.get("features"), dict) else {}
        risk = payload.get("risk") if isinstance(payload.get("risk"), dict) else {}
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
                "input_schema_version": risk.get("input_schema_version"),
                "backend": risk.get("backend"),
                "top_contribution_1": _format_contribution(contributions, 0),
                "top_contribution_2": _format_contribution(contributions, 1),
                "top_contribution_3": _format_contribution(contributions, 2),
                "created_at": analysis.created_at,
            }
        )

    filename = f"patient-{patient_id}-research-table.csv" if patient_id else "research-table.csv"
    return _csv_response(filename, RESEARCH_FIELDS, rows)
