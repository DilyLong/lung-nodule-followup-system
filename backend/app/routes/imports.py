from __future__ import annotations

import csv
import io
import json
from datetime import date, datetime
from typing import Any

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ImportBatch, ImportBatchEntity, Nodule, NoduleMeasurement, Patient, Study
from ..schemas import ImportBatchDetail, ImportBatchRead, ImportCommitCounts, ImportCommitReport, ImportFileValidationSummary, ImportPreviewReport, ImportValidationIssue, ImportValidationReport, ImportValidationSummary

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
            "optional_columns": ["name", "smoking_history", "family_history", "primary_diagnosis", "clinical_label", "malignancy_confirmed", "surgery_date", "pathology_result"],
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
            "optional_columns": ["volume_mm3", "mean_hu", "min_hu", "max_hu", "roi_area_mm2", "solid_component_percent", "spiculation_score", "lobulation_score", "pleural_retraction_score", "measurement_source"],
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
    "future_import_endpoint": {"planned": False, "scope": "Validation, preview, commit, batch history and rollback are available."},
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
    "nodules.csv": {"nodule_type": "nodule_type", "clinical_label": "clinical_label", "pathology_label": "pathology_label"},
    "measurements.csv": {"measurement_source": "measurement_source"},
}
DATE_FIELDS = {"patients.csv": ["surgery_date"], "studies.csv": ["study_date"], "measurements.csv": ["study_date"]}


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
    return [{(key or "").strip(): (value or "").strip() for key, value in row.items()} for row in reader], headers


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
                issues.append(_issue(file_name, "error", "数值格式不正确" if kind not in {"int", "positive_float"} else "应为非负整数" if kind == "int" else "应为大于 0 的数字", index, column))


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
    return {"patients.csv": patients, "studies.csv": studies, "nodules.csv": nodules, "measurements.csv": measurements}


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
    return ImportValidationReport(valid=error_count == 0, summary=ImportValidationSummary(file_count=len(REQUIRED_IMPORT_FILES), total_rows=sum(summary.row_count for summary in file_summaries), error_count=error_count, warning_count=warning_count), files=file_summaries, issues=issues), data


def _value(row: dict[str, str], key: str, default: Any = "") -> Any:
    return row.get(key) or default


def _float_value(row: dict[str, str], key: str, default: float | None) -> float | None:
    value = row.get(key, "")
    return float(value) if value != "" else default


def _int_value(row: dict[str, str], key: str, default: int) -> int:
    value = row.get(key, "")
    return int(value) if value != "" else default


def _date_value(row: dict[str, str], key: str) -> date:
    return datetime.strptime(row[key], "%Y-%m-%d").date()


def _snapshot(obj: Any, fields: list[str]) -> str:
    return json.dumps({field: getattr(obj, field) for field in fields}, ensure_ascii=False, default=str)


def _track(db: Session, batch: ImportBatch | None, entity_type: str, entity_id: int, action: str, stable_key: str, previous: str | None, operator: str = "系统") -> None:
    if batch:
        db.add(ImportBatchEntity(batch_id=batch.id, entity_type=entity_type, entity_id=entity_id, action=action, stable_key=stable_key, previous_json=previous, operator=operator))


def _qc_issues(data: dict[str, list[dict[str, str]]]) -> list[ImportValidationIssue]:
    issues: list[ImportValidationIssue] = []
    measurements_by_nodule: dict[tuple[str, str], list[dict[str, str]]] = {}
    study_paths = {(row["patient_code"], row["study_date"]): row.get("dicom_relative_path", "") for row in data["studies.csv"]}
    for row in data["studies.csv"]:
        if not row.get("dicom_relative_path"):
            issues.append(_issue("studies.csv", "warning", "检查缺少 DICOM 路径，后续只能使用结构化测量", column="dicom_relative_path"))
    for row in data["measurements.csv"]:
        measurements_by_nodule.setdefault((row["patient_code"], row["nodule_id"]), []).append(row)
        if study_paths.get((row["patient_code"], row["study_date"]), "") == "":
            issues.append(_issue("measurements.csv", "warning", "该测量对应检查未关联 DICOM 路径", column="study_date"))
    for (patient_code, nodule_id), rows in measurements_by_nodule.items():
        ordered = sorted(rows, key=lambda item: item["study_date"])
        if len(ordered) < 2:
            issues.append(_issue("measurements.csv", "warning", f"{patient_code}/{nodule_id} 随访测量少于 2 期"))
        for previous, current in zip(ordered, ordered[1:]):
            days = (_date_value(current, "study_date") - _date_value(previous, "study_date")).days
            if days <= 0:
                issues.append(_issue("measurements.csv", "error", f"{patient_code}/{nodule_id} 检查日期未递增", column="study_date"))
            if days > 3650:
                issues.append(_issue("measurements.csv", "warning", f"{patient_code}/{nodule_id} 随访间隔超过 10 年", column="study_date"))
            prev_d = float(previous["diameter_mm"])
            cur_d = float(current["diameter_mm"])
            if prev_d and abs(cur_d - prev_d) / prev_d > 2:
                issues.append(_issue("measurements.csv", "warning", f"{patient_code}/{nodule_id} 最大径跳变超过 200%", column="diameter_mm"))
    return issues


def _qc_score(qc_issues: list[ImportValidationIssue]) -> float:
    penalty = sum(18 if issue.severity == "error" else 6 for issue in qc_issues)
    return max(0.0, round(100.0 - penalty, 1))


def _preview_counts(data: dict[str, list[dict[str, str]]], db: Session) -> ImportCommitCounts:
    counts = ImportCommitCounts()
    for row in data["patients.csv"]:
        if db.query(Patient).filter(Patient.patient_code == row["patient_code"]).first():
            counts.patients_updated += 1
        else:
            counts.patients_created += 1
    patient_ids = {patient.patient_code: patient.id for patient in db.query(Patient).filter(Patient.patient_code.in_([row["patient_code"] for row in data["patients.csv"]])).all()}
    for row in data["studies.csv"]:
        patient_id = patient_ids.get(row["patient_code"])
        exists = patient_id and db.query(Study).filter(Study.patient_id == patient_id, Study.study_date == _date_value(row, "study_date")).first()
        counts.studies_updated += 1 if exists else 0
        counts.studies_created += 0 if exists else 1
    for row in data["nodules.csv"]:
        patient_id = patient_ids.get(row["patient_code"])
        label = _value(row, "nodule_label", row["nodule_id"])
        exists = patient_id and db.query(Nodule).filter(Nodule.patient_id == patient_id, Nodule.label.in_([row["nodule_id"], label])).first()
        counts.nodules_updated += 1 if exists else 0
        counts.nodules_created += 0 if exists else 1
    counts.measurements_created = len(data["measurements.csv"])
    return counts


def _upsert_import_data(data: dict[str, list[dict[str, str]]], db: Session, batch: ImportBatch | None = None, operator: str = "系统") -> tuple[ImportCommitCounts, list[int]]:
    counts = ImportCommitCounts()
    patients_by_code: dict[str, Patient] = {}
    studies_by_key: dict[tuple[str, str], Study] = {}
    nodules_by_key: dict[tuple[str, str], Nodule] = {}
    for row in data["patients.csv"]:
        code = row["patient_code"]
        patient = db.query(Patient).filter(Patient.patient_code == code).first()
        if patient:
            previous = _snapshot(patient, ["name", "sex", "age", "smoking_history", "family_history", "primary_diagnosis"])
            counts.patients_updated += 1
            action = "updated"
        else:
            patient = Patient(
                patient_code=code,
                name=_value(row, "name", code),
                sex=row["sex"],
                age=_int_value(row, "age", 0),
                smoking_history=_value(row, "smoking_history", "未记录"),
                family_history=_value(row, "family_history", "无"),
                primary_diagnosis=_value(row, "primary_diagnosis", "肺结节随访"),
            )
            db.add(patient)
            db.flush()
            previous = None
            counts.patients_created += 1
            action = "created"
        patient.name = _value(row, "name", code)
        patient.sex = row["sex"]
        patient.age = _int_value(row, "age", patient.age)
        patient.smoking_history = _value(row, "smoking_history", "未记录")
        patient.family_history = _value(row, "family_history", "无")
        patient.primary_diagnosis = _value(row, "primary_diagnosis", "肺结节随访")
        patients_by_code[code] = patient
        _track(db, batch, "patient", patient.id, action, code, previous, operator)
    db.flush()
    for row in data["studies.csv"]:
        patient = patients_by_code[row["patient_code"]]
        study_date = _date_value(row, "study_date")
        study = db.query(Study).filter(Study.patient_id == patient.id, Study.study_date == study_date).first()
        if study:
            previous = _snapshot(study, ["modality", "scanner", "slice_thickness_mm", "series_description", "file_name", "status"])
            counts.studies_updated += 1
            action = "updated"
        else:
            study = Study(patient_id=patient.id, study_date=study_date)
            db.add(study)
            db.flush()
            previous = None
            counts.studies_created += 1
            action = "created"
        study.modality = _value(row, "modality", "CT")
        study.scanner = _value(row, "scanner", "CSV 导入 CT")
        study.slice_thickness_mm = _float_value(row, "slice_thickness_mm", 1.0) or 1.0
        study.series_description = _value(row, "series_description", _value(row, "series_instance_uid", "CSV 导入检查"))
        study.file_name = _value(row, "dicom_relative_path", None) or None
        study.status = "CSV 已导入，待 DICOM 关联"
        studies_by_key[(row["patient_code"], row["study_date"])] = study
        _track(db, batch, "study", study.id, action, f"{row['patient_code']}|{row['study_date']}", previous, operator)
    db.flush()
    for row in data["nodules.csv"]:
        patient = patients_by_code[row["patient_code"]]
        label = _value(row, "nodule_label", row["nodule_id"])
        nodule = db.query(Nodule).filter(Nodule.patient_id == patient.id, Nodule.label.in_([row["nodule_id"], label])).first()
        if nodule:
            previous = _snapshot(nodule, ["label", "lobe", "nodule_type", "clinical_label", "pathology_label", "baseline_impression"])
            counts.nodules_updated += 1
            action = "updated"
        else:
            nodule = Nodule(patient_id=patient.id, label=label, lobe=row["lobe"], nodule_type=row["nodule_type"], clinical_label=_value(row, "clinical_label", "待定"), pathology_label=_value(row, "pathology_label", "未手术"), baseline_impression="")
            db.add(nodule)
            db.flush()
            previous = None
            counts.nodules_created += 1
            action = "created"
        nodule.label = label
        nodule.lobe = row["lobe"]
        nodule.nodule_type = row["nodule_type"]
        nodule.clinical_label = _value(row, "clinical_label", "待定")
        nodule.pathology_label = _value(row, "pathology_label", "未手术")
        nodule.baseline_impression = _value(row, "baseline_impression", "CSV 导入结节")
        nodules_by_key[(row["patient_code"], row["nodule_id"])] = nodule
        _track(db, batch, "nodule", nodule.id, action, f"{row['patient_code']}|{row['nodule_id']}", previous, operator)
    db.flush()
    for row in data["measurements.csv"]:
        nodule = nodules_by_key[(row["patient_code"], row["nodule_id"])]
        study = studies_by_key[(row["patient_code"], row["study_date"])]
        measurement = db.query(NoduleMeasurement).filter(NoduleMeasurement.nodule_id == nodule.id, NoduleMeasurement.study_id == study.id).first()
        if measurement:
            previous = _snapshot(measurement, ["diameter_mm", "volume_mm3", "mean_hu", "min_hu", "max_hu", "roi_area_mm2", "solid_component_percent", "spiculation_score", "lobulation_score", "pleural_retraction_score", "measurement_source"])
            counts.measurements_updated += 1
            action = "updated"
        else:
            measurement = NoduleMeasurement(
                nodule_id=nodule.id,
                study_id=study.id,
                diameter_mm=_float_value(row, "diameter_mm", 1.0) or 1.0,
                volume_mm3=_float_value(row, "volume_mm3", 1.0) or 1.0,
                mean_hu=_float_value(row, "mean_hu", -600.0 if "磨玻璃" in nodule.nodule_type else 40.0) or 0.0,
                solid_component_percent=_float_value(row, "solid_component_percent", 0.0) or 0.0,
                spiculation_score=_float_value(row, "spiculation_score", 0.0) or 0.0,
                lobulation_score=_float_value(row, "lobulation_score", 0.0) or 0.0,
                pleural_retraction_score=_float_value(row, "pleural_retraction_score", 0.0) or 0.0,
                thumbnail_seed=study.id,
                measurement_source=_value(row, "measurement_source", "imported_research_table"),
            )
            db.add(measurement)
            db.flush()
            previous = None
            counts.measurements_created += 1
            action = "created"
        measurement.diameter_mm = _float_value(row, "diameter_mm", 1.0) or 1.0
        measurement.volume_mm3 = _float_value(row, "volume_mm3", round(4 / 3 * 3.14159 * (measurement.diameter_mm / 2) ** 3, 2)) or 0.0
        measurement.mean_hu = _float_value(row, "mean_hu", -600.0 if "磨玻璃" in nodule.nodule_type else 40.0) or 0.0
        measurement.min_hu = _float_value(row, "min_hu", None)
        measurement.max_hu = _float_value(row, "max_hu", None)
        measurement.roi_area_mm2 = _float_value(row, "roi_area_mm2", None)
        measurement.solid_component_percent = _float_value(row, "solid_component_percent", 0.0) or 0.0
        measurement.spiculation_score = _float_value(row, "spiculation_score", 0.0) or 0.0
        measurement.lobulation_score = _float_value(row, "lobulation_score", 0.0) or 0.0
        measurement.pleural_retraction_score = _float_value(row, "pleural_retraction_score", 0.0) or 0.0
        measurement.measurement_source = _value(row, "measurement_source", "imported_research_table")
        _track(db, batch, "measurement", measurement.id, action, f"{row['patient_code']}|{row['study_date']}|{row['nodule_id']}", previous, operator)
    db.flush()
    return counts, [patient.id for patient in patients_by_code.values()]


def _batch_report(batch: ImportBatch, entities: list[ImportBatchEntity] | None = None) -> ImportBatchRead | ImportBatchDetail:
    if entities is None:
        return ImportBatchRead.model_validate(batch)
    return ImportBatchDetail(batch=ImportBatchRead.model_validate(batch), entities=[entity for entity in entities])


def _rollback_entity(entity: ImportBatchEntity, db: Session) -> None:
    model_map = {"measurement": NoduleMeasurement, "nodule": Nodule, "study": Study, "patient": Patient}
    model = model_map[entity.entity_type]
    obj = db.get(model, entity.entity_id)
    if entity.action == "created":
        if obj:
            db.delete(obj)
        return
    if entity.action == "updated" and obj and entity.previous_json:
        for key, value in json.loads(entity.previous_json).items():
            if key.endswith("_date") and isinstance(value, str):
                value = datetime.fromisoformat(value).date()
            setattr(obj, key, value)


@router.get("/spec")
def import_spec() -> dict:
    return DATASET_SPEC


@router.post("/validate", response_model=ImportValidationReport)
def validate_import_dataset(patients: UploadFile = File(...), studies: UploadFile = File(...), nodules: UploadFile = File(...), measurements: UploadFile = File(...)) -> ImportValidationReport:
    report, _ = _validate_uploaded_files(_uploaded_file_map(patients, studies, nodules, measurements))
    return report


@router.post("/preview", response_model=ImportPreviewReport)
def preview_import_dataset(patients: UploadFile = File(...), studies: UploadFile = File(...), nodules: UploadFile = File(...), measurements: UploadFile = File(...), db: Session = Depends(get_db)) -> ImportPreviewReport:
    report, data = _validate_uploaded_files(_uploaded_file_map(patients, studies, nodules, measurements))
    qc = _qc_issues(data) if report.valid else []
    return ImportPreviewReport(validation=report, counts=_preview_counts(data, db) if report.valid else ImportCommitCounts(), qc_score=_qc_score(qc), qc_issues=qc, message="预览完成，可确认导入。" if report.valid else "CSV 存在错误，请修正后再预览。")


@router.post("/commit", response_model=ImportCommitReport)
def commit_import_dataset(patients: UploadFile = File(...), studies: UploadFile = File(...), nodules: UploadFile = File(...), measurements: UploadFile = File(...), operator: str = "系统", db: Session = Depends(get_db)) -> ImportCommitReport:
    report, data = _validate_uploaded_files(_uploaded_file_map(patients, studies, nodules, measurements))
    empty_counts = ImportCommitCounts()
    qc = _qc_issues(data) if report.valid else []
    batch = ImportBatch(status="failed" if not report.valid else "committed", qc_score=_qc_score(qc), issues_json=json.dumps([issue.model_dump() for issue in qc], ensure_ascii=False), message="CSV 存在错误，未写入数据库。" if not report.valid else "CSV 队列已导入数据库，可在病例工作台查看。", operator=operator)
    db.add(batch)
    db.flush()
    if not report.valid:
        db.commit()
        return ImportCommitReport(committed=False, validation=report, counts=empty_counts, patient_ids=[], message=batch.message, batch=batch)
    counts, patient_ids = _upsert_import_data(data, db, batch, operator)
    batch.counts_json = counts.model_dump_json()
    batch.committed_at = datetime.utcnow()
    db.commit()
    return ImportCommitReport(committed=True, validation=report, counts=counts, patient_ids=patient_ids, message=batch.message, batch=batch)


@router.get("/batches", response_model=list[ImportBatchRead])
def list_import_batches(db: Session = Depends(get_db)) -> list[ImportBatch]:
    return db.query(ImportBatch).order_by(ImportBatch.created_at.desc()).limit(20).all()


@router.get("/batches/{batch_id}", response_model=ImportBatchDetail)
def get_import_batch(batch_id: int, db: Session = Depends(get_db)) -> ImportBatchDetail:
    batch = db.get(ImportBatch, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Import batch not found")
    entities = db.query(ImportBatchEntity).filter(ImportBatchEntity.batch_id == batch_id).order_by(ImportBatchEntity.id).all()
    return ImportBatchDetail(batch=batch, entities=entities)


@router.post("/batches/{batch_id}/rollback", response_model=ImportBatchRead)
def rollback_import_batch(batch_id: int, operator: str = "系统", db: Session = Depends(get_db)) -> ImportBatch:
    batch = db.get(ImportBatch, batch_id)
    if not batch:
        raise HTTPException(status_code=404, detail="Import batch not found")
    if batch.status != "committed":
        raise HTTPException(status_code=400, detail="Only committed batches can be rolled back")
    entities = db.query(ImportBatchEntity).filter(ImportBatchEntity.batch_id == batch_id).order_by(ImportBatchEntity.id.desc()).all()
    for entity in entities:
        _rollback_entity(entity, db)
    batch.status = "rolled_back"
    batch.operator = operator
    batch.rolled_back_at = datetime.utcnow()
    db.commit()
    db.refresh(batch)
    return batch
