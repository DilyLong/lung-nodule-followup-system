from __future__ import annotations

import csv
import io
from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends, File, UploadFile
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Nodule, NoduleMeasurement, Patient, Study
from ..schemas import ImportCommitCounts, ImportCommitReport, ImportFileValidationSummary, ImportValidationIssue, ImportValidationReport, ImportValidationSummary

router = APIRouter(prefix="/imports", tags=["imports"])

DATASET_SPEC = {
    "spec_version": "lung-nodule-dataset-v1",
    "date_format": "YYYY-MM-DD",
    "coordinate_system": {
        "slice_coordinates": "image pixel coordinates or percent coordinates",
        "x_percent": "0-100, left to right on rendered axial slice",
        "y_percent": "0-100, top to bottom on rendered axial slice",
        "diameter_unit": "mm",
        "volume_unit": "mm3",
        "density_unit": "HU",
    },
    "dicom_layout": {
        "root": "dicom_root/{patient_code}/{study_date}/{series_uid_or_name}/...dcm",
        "study_date": "Must match studies.csv study_date",
        "series_uid_or_name": "Use SeriesInstanceUID when available; otherwise a stable local series folder name",
        "multi_phase_rule": "One folder per CT follow-up time point. Keep all axial slices from the same acquisition in the same series folder.",
    },
    "files": {
        "patients.csv": {
            "required_columns": ["patient_code", "sex", "age"],
            "optional_columns": [
                "name",
                "smoking_history",
                "family_history",
                "primary_diagnosis",
                "clinical_label",
                "malignancy_confirmed",
                "surgery_date",
                "pathology_result",
            ],
            "notes": "patient_code must be stable and de-identified before model training or external research export.",
        },
        "studies.csv": {
            "required_columns": ["patient_code", "study_date", "modality", "dicom_relative_path"],
            "optional_columns": ["scanner", "slice_thickness_mm", "series_description", "series_instance_uid"],
            "notes": "Each row is one CT time point. dicom_relative_path is relative to dicom_root.",
        },
        "nodules.csv": {
            "required_columns": ["patient_code", "nodule_id", "nodule_label", "lobe", "nodule_type"],
            "optional_columns": ["baseline_impression", "clinical_label", "pathology_label"],
            "notes": "nodule_id must remain stable across follow-up studies for the same physical nodule.",
        },
        "measurements.csv": {
            "required_columns": ["patient_code", "study_date", "nodule_id", "diameter_mm"],
            "optional_columns": [
                "volume_mm3",
                "mean_hu",
                "min_hu",
                "max_hu",
                "roi_area_mm2",
                "solid_component_percent",
                "spiculation_score",
                "lobulation_score",
                "pleural_retraction_score",
                "measurement_source",
            ],
            "notes": "Use one row per nodule per CT time point. Keep missing ROI fields empty rather than using sentinel values.",
        },
        "annotations.csv": {
            "required_columns": ["patient_code", "study_date", "nodule_id", "slice_identifier", "x_percent", "y_percent", "diameter_mm"],
            "optional_columns": ["instance_number", "slice_location", "nodule_type", "note", "roi_mask_relative_path"],
            "notes": "Optional but recommended for reproducible ROI extraction and cross-reader quality review.",
        },
    },
    "allowed_values": {
        "sex": ["男", "女", "其他", "未知"],
        "modality": ["CT", "LDCT"],
        "nodule_type": ["纯磨玻璃", "部分实性", "实性", "钙化", "未分类"],
        "clinical_label": ["稳定", "进展", "缩小", "恶性", "良性", "待定"],
        "pathology_label": ["AIS", "MIA", "浸润性腺癌", "鳞癌", "小细胞肺癌", "转移瘤", "良性", "未手术"],
        "measurement_source": ["manual_annotation", "radiologist_report", "segmentation_model", "imported_research_table"],
    },
    "quality_checks": [
        "Every study row should have at least one DICOM series folder.",
        "Each nodule_id should map to one anatomical nodule within a patient.",
        "Measurements for a nodule should be ordered by study_date and use consistent units.",
        "Pathology labels should be separated from model input columns during validation to avoid leakage.",
        "De-identify DICOM headers before sharing data outside the clinical environment.",
    ],
    "future_import_endpoint": {
        "planned": True,
        "scope": "Batch validation and database import will use this spec as the contract; this version only exposes the contract.",
    },
}

REQUIRED_IMPORT_FILES = ["patients.csv", "studies.csv", "nodules.csv", "measurements.csv"]
NUMERIC_FIELDS = {
    "patients.csv": {"age": "int"},
    "measurements.csv": {
        "diameter_mm": "positive_float",
        "volume_mm3": "float",
        "mean_hu": "float",
        "min_hu": "float",
        "max_hu": "float",
        "roi_area_mm2": "float",
        "solid_component_percent": "float",
        "spiculation_score": "float",
        "lobulation_score": "float",
        "pleural_retraction_score": "float",
    },
}
ENUM_FIELDS = {
    "patients.csv": {"sex": "sex"},
    "studies.csv": {"modality": "modality"},
    "nodules.csv": {"nodule_type": "nodule_type"},
    "measurements.csv": {"measurement_source": "measurement_source"},
}
DATE_FIELDS = {
    "patients.csv": ["surgery_date"],
    "studies.csv": ["study_date"],
    "measurements.csv": ["study_date"],
}


def _issue(file_name: str, severity: str, message: str, row: int | None = None, column: str | None = None) -> ImportValidationIssue:
    return ImportValidationIssue(file=file_name, row=row, column=column, severity=severity, message=message)


def _read_csv(file_name: str, file: UploadFile, issues: list[ImportValidationIssue]) -> tuple[list[dict[str, str]], list[str]]:
    try:
        content = file.file.read().decode("utf-8-sig")
    except UnicodeDecodeError:
        issues.append(_issue(file_name, "error", "CSV 文件必须使用 UTF-8 或 UTF-8 BOM 编码"))
        return [], []
    reader = csv.DictReader(io.StringIO(content))
    if not reader.fieldnames:
        issues.append(_issue(file_name, "error", "CSV 文件为空或缺少表头"))
        return [], []
    headers = [header.strip() for header in reader.fieldnames if header]
    rows = []
    for row in reader:
        rows.append({(key or "").strip(): (value or "").strip() for key, value in row.items()})
    return rows, headers


def _validate_date(value: str) -> bool:
    try:
        datetime.strptime(value, "%Y-%m-%d")
    except ValueError:
        return False
    return True


def _validate_number(value: str, kind: str) -> bool:
    if value == "":
        return True
    try:
        parsed = int(value) if kind == "int" else float(value)
    except ValueError:
        return False
    if kind == "int" and parsed < 0:
        return False
    return not (kind == "positive_float" and parsed <= 0)


def _validate_headers(file_name: str, headers: list[str], issues: list[ImportValidationIssue]) -> ImportFileValidationSummary:
    spec = DATASET_SPEC["files"][file_name]
    required = set(spec["required_columns"])
    allowed = required | set(spec["optional_columns"])
    missing = sorted(required - set(headers))
    unknown = sorted(set(headers) - allowed)
    for column in missing:
        issues.append(_issue(file_name, "error", "缺少必填字段", column=column))
    for column in unknown:
        issues.append(_issue(file_name, "warning", "字段不在当前导入规范中，将在后续导入时忽略", column=column))
    return ImportFileValidationSummary(file=file_name, row_count=0, missing_required_columns=missing, unknown_columns=unknown)


def _validate_rows(file_name: str, rows: list[dict[str, str]], issues: list[ImportValidationIssue]) -> None:
    spec = DATASET_SPEC["files"][file_name]
    allowed_values = DATASET_SPEC["allowed_values"]
    for index, row in enumerate(rows, start=2):
        for column in spec["required_columns"]:
            if not row.get(column):
                issues.append(_issue(file_name, "error", "必填字段不能为空", index, column))
        for column, enum_key in ENUM_FIELDS.get(file_name, {}).items():
            value = row.get(column, "")
            if value and value not in allowed_values[enum_key]:
                issues.append(_issue(file_name, "error", f"取值不在允许范围：{', '.join(allowed_values[enum_key])}", index, column))
        for column in DATE_FIELDS.get(file_name, []):
            value = row.get(column, "")
            if value and not _validate_date(value):
                issues.append(_issue(file_name, "error", "日期格式应为 YYYY-MM-DD", index, column))
        for column, kind in NUMERIC_FIELDS.get(file_name, {}).items():
            value = row.get(column, "")
            if value and not _validate_number(value, kind):
                message = "数值格式不正确"
                if kind == "int":
                    message = "应为非负整数"
                elif kind == "positive_float":
                    message = "应为大于 0 的数字"
                issues.append(_issue(file_name, "error", message, index, column))


def _validate_unique(rows: list[dict[str, str]], file_name: str, key_columns: list[str], issues: list[ImportValidationIssue]) -> set[tuple[str, ...]]:
    seen: set[tuple[str, ...]] = set()
    for index, row in enumerate(rows, start=2):
        key = tuple(row.get(column, "") for column in key_columns)
        if any(not value for value in key):
            continue
        if key in seen:
            issues.append(_issue(file_name, "error", f"重复键：{' + '.join(key_columns)}", index, "+".join(key_columns)))
        seen.add(key)
    return seen


def _validate_references(data: dict[str, list[dict[str, str]]], issues: list[ImportValidationIssue]) -> None:
    patients = _validate_unique(data["patients.csv"], "patients.csv", ["patient_code"], issues)
    studies = _validate_unique(data["studies.csv"], "studies.csv", ["patient_code", "study_date"], issues)
    nodules = _validate_unique(data["nodules.csv"], "nodules.csv", ["patient_code", "nodule_id"], issues)
    _validate_unique(data["measurements.csv"], "measurements.csv", ["patient_code", "study_date", "nodule_id"], issues)

    for file_name in ["studies.csv", "nodules.csv", "measurements.csv"]:
        for index, row in enumerate(data[file_name], start=2):
            patient_key = (row.get("patient_code", ""),)
            if patient_key != ("",) and patient_key not in patients:
                issues.append(_issue(file_name, "error", "patient_code 未在 patients.csv 中定义", index, "patient_code"))

    for index, row in enumerate(data["measurements.csv"], start=2):
        study_key = (row.get("patient_code", ""), row.get("study_date", ""))
        nodule_key = (row.get("patient_code", ""), row.get("nodule_id", ""))
        if all(study_key) and study_key not in studies:
            issues.append(_issue("measurements.csv", "error", "测量记录未匹配到 studies.csv 中的检查日期", index, "study_date"))
        if all(nodule_key) and nodule_key not in nodules:
            issues.append(_issue("measurements.csv", "error", "测量记录未匹配到 nodules.csv 中的结节 ID", index, "nodule_id"))


def _uploaded_file_map(patients: UploadFile, studies: UploadFile, nodules: UploadFile, measurements: UploadFile) -> dict[str, UploadFile]:
    return {
        "patients.csv": patients,
        "studies.csv": studies,
        "nodules.csv": nodules,
        "measurements.csv": measurements,
    }


def _validate_uploaded_files(uploaded_files: dict[str, UploadFile]) -> tuple[ImportValidationReport, dict[str, list[dict[str, str]]]]:
    issues: list[ImportValidationIssue] = []
    file_summaries: list[ImportFileValidationSummary] = []
    data: dict[str, list[dict[str, str]]] = {}

    for file_name in REQUIRED_IMPORT_FILES:
        uploaded_files[file_name].file.seek(0)
        rows, headers = _read_csv(file_name, uploaded_files[file_name], issues)
        summary = _validate_headers(file_name, headers, issues)
        summary.row_count = len(rows)
        file_summaries.append(summary)
        data[file_name] = rows
        _validate_rows(file_name, rows, issues)

    _validate_references(data, issues)
    error_count = sum(1 for issue in issues if issue.severity == "error")
    warning_count = sum(1 for issue in issues if issue.severity == "warning")
    report = ImportValidationReport(
        valid=error_count == 0,
        summary=ImportValidationSummary(
            file_count=len(REQUIRED_IMPORT_FILES),
            total_rows=sum(summary.row_count for summary in file_summaries),
            error_count=error_count,
            warning_count=warning_count,
        ),
        files=file_summaries,
        issues=issues,
    )
    return report, data


def _value(row: dict[str, str], key: str, default: str = "") -> str:
    return row.get(key) or default


def _float_value(row: dict[str, str], key: str, default: float) -> float:
    value = row.get(key, "")
    return float(value) if value != "" else default


def _int_value(row: dict[str, str], key: str, default: int) -> int:
    value = row.get(key, "")
    return int(value) if value != "" else default


def _date_value(row: dict[str, str], key: str) -> date:
    return datetime.strptime(row[key], "%Y-%m-%d").date()


def _upsert_import_data(data: dict[str, list[dict[str, str]]], db: Session) -> tuple[ImportCommitCounts, list[int]]:
    counts = ImportCommitCounts()
    patients_by_code: dict[str, Patient] = {}
    studies_by_key: dict[tuple[str, str], Study] = {}
    nodules_by_key: dict[tuple[str, str], Nodule] = {}

    for row in data["patients.csv"]:
        patient_code = row["patient_code"]
        patient = db.query(Patient).filter(Patient.patient_code == patient_code).first()
        if patient:
            counts.patients_updated += 1
        else:
            patient = Patient(patient_code=patient_code, name=_value(row, "name", patient_code), sex=row["sex"], age=_int_value(row, "age", 0))
            db.add(patient)
            counts.patients_created += 1
        patient.name = _value(row, "name", patient_code)
        patient.sex = row["sex"]
        patient.age = _int_value(row, "age", patient.age)
        patient.smoking_history = _value(row, "smoking_history", "未记录")
        patient.family_history = _value(row, "family_history", "无")
        patient.primary_diagnosis = _value(row, "primary_diagnosis", "肺结节随访")
        patients_by_code[patient_code] = patient
    db.flush()

    for row in data["studies.csv"]:
        patient = patients_by_code[row["patient_code"]]
        study_date = _date_value(row, "study_date")
        study = db.query(Study).filter(Study.patient_id == patient.id, Study.study_date == study_date).first()
        if study:
            counts.studies_updated += 1
        else:
            study = Study(patient_id=patient.id, study_date=study_date)
            db.add(study)
            counts.studies_created += 1
        study.modality = _value(row, "modality", "CT")
        study.scanner = _value(row, "scanner", "CSV 导入 CT")
        study.slice_thickness_mm = _float_value(row, "slice_thickness_mm", 1.0)
        study.series_description = _value(row, "series_description", _value(row, "series_instance_uid", "CSV 导入检查"))
        study.file_name = _value(row, "dicom_relative_path", None) or None
        study.status = "CSV 已导入，待 DICOM 关联"
        studies_by_key[(row["patient_code"], row["study_date"])] = study
    db.flush()

    for row in data["nodules.csv"]:
        patient = patients_by_code[row["patient_code"]]
        nodule = (
            db.query(Nodule)
            .filter(Nodule.patient_id == patient.id, Nodule.label.in_([row["nodule_id"], _value(row, "nodule_label", row["nodule_id"])]))
            .first()
        )
        if nodule:
            counts.nodules_updated += 1
        else:
            nodule = Nodule(patient_id=patient.id, label=row["nodule_id"], lobe=row["lobe"], nodule_type=row["nodule_type"], baseline_impression="")
            db.add(nodule)
            counts.nodules_created += 1
        nodule.label = _value(row, "nodule_label", row["nodule_id"])
        nodule.lobe = row["lobe"]
        nodule.nodule_type = row["nodule_type"]
        nodule.baseline_impression = _value(row, "baseline_impression", "CSV 导入结节")
        nodules_by_key[(row["patient_code"], row["nodule_id"])] = nodule
    db.flush()

    for row in data["measurements.csv"]:
        nodule = nodules_by_key[(row["patient_code"], row["nodule_id"])]
        study = studies_by_key[(row["patient_code"], row["study_date"])]
        measurement = db.query(NoduleMeasurement).filter(NoduleMeasurement.nodule_id == nodule.id, NoduleMeasurement.study_id == study.id).first()
        if measurement:
            counts.measurements_updated += 1
        else:
            measurement = NoduleMeasurement(nodule_id=nodule.id, study_id=study.id, thumbnail_seed=study.id)
            db.add(measurement)
            counts.measurements_created += 1
        measurement.diameter_mm = _float_value(row, "diameter_mm", 1.0)
        measurement.volume_mm3 = _float_value(row, "volume_mm3", round(4 / 3 * 3.14159 * (measurement.diameter_mm / 2) ** 3, 2))
        measurement.mean_hu = _float_value(row, "mean_hu", -600.0 if "磨玻璃" in nodule.nodule_type else 40.0)
        measurement.min_hu = _float_value(row, "min_hu", None) if row.get("min_hu") else None
        measurement.max_hu = _float_value(row, "max_hu", None) if row.get("max_hu") else None
        measurement.roi_area_mm2 = _float_value(row, "roi_area_mm2", None) if row.get("roi_area_mm2") else None
        measurement.solid_component_percent = _float_value(row, "solid_component_percent", 0.0)
        measurement.spiculation_score = _float_value(row, "spiculation_score", 0.0)
        measurement.lobulation_score = _float_value(row, "lobulation_score", 0.0)
        measurement.pleural_retraction_score = _float_value(row, "pleural_retraction_score", 0.0)
    db.flush()
    return counts, [patient.id for patient in patients_by_code.values()]
@router.get("/spec")
def import_spec() -> dict:
    return DATASET_SPEC


@router.post("/validate", response_model=ImportValidationReport)
def validate_import_dataset(
    patients: UploadFile = File(...),
    studies: UploadFile = File(...),
    nodules: UploadFile = File(...),
    measurements: UploadFile = File(...),
) -> ImportValidationReport:
    report, _ = _validate_uploaded_files(_uploaded_file_map(patients, studies, nodules, measurements))
    return report


@router.post("/commit", response_model=ImportCommitReport)
def commit_import_dataset(
    patients: UploadFile = File(...),
    studies: UploadFile = File(...),
    nodules: UploadFile = File(...),
    measurements: UploadFile = File(...),
    db: Session = Depends(get_db),
) -> ImportCommitReport:
    report, data = _validate_uploaded_files(_uploaded_file_map(patients, studies, nodules, measurements))
    empty_counts = ImportCommitCounts()
    if not report.valid:
        return ImportCommitReport(committed=False, validation=report, counts=empty_counts, patient_ids=[], message="CSV 存在错误，未写入数据库。")
    counts, patient_ids = _upsert_import_data(data, db)
    db.commit()
    return ImportCommitReport(committed=True, validation=report, counts=counts, patient_ids=patient_ids, message="CSV 队列已导入数据库，可在病例工作台查看。")
