from __future__ import annotations

from datetime import date
from math import pi
from typing import Any

from sqlalchemy.orm import Session

from .models import Nodule, NoduleMeasurement, Patient, Study

SYNTHETIC_DEMO_CASES: list[dict[str, Any]] = [
    {
        "patient": {"patient_code": "SYN-LN-2026-001", "name": "示例患者01", "sex": "女", "age": 58, "smoking_history": "无吸烟史", "family_history": "无肺癌家族史", "primary_diagnosis": "Synthetic demo：右上肺部分实性结节进展随访"},
        "nodules": [
            {"label": "主结节", "lobe": "右上叶尖段", "nodule_type": "部分实性", "clinical_label": "进展", "pathology_label": "MIA", "baseline_impression": "部分实性磨玻璃结节，实性成分逐渐增加", "diameters": [8.1, 9.2, 10.8], "mean_hu": [-515, -468, -390], "solid": [18, 27, 40], "morph": [0.18, 0.28, 0.48]},
            {"label": "副结节A", "lobe": "右中叶外侧段", "nodule_type": "纯磨玻璃", "clinical_label": "稳定", "pathology_label": "未手术", "baseline_impression": "小纯磨玻璃结节，长期稳定", "diameters": [4.1, 4.2, 4.2], "mean_hu": [-690, -685, -682], "solid": [0, 0, 0], "morph": [0.05, 0.05, 0.05]},
        ],
    },
    {
        "patient": {"patient_code": "SYN-LN-2026-002", "name": "示例患者02", "sex": "男", "age": 66, "smoking_history": "吸烟 30 包年，已戒烟", "family_history": "父亲肺癌史", "primary_diagnosis": "Synthetic demo：左下肺实性结节稳定随访"},
        "nodules": [
            {"label": "主结节", "lobe": "左下叶背段", "nodule_type": "实性", "clinical_label": "稳定", "pathology_label": "良性", "baseline_impression": "实性小结节，高危背景下随访稳定", "diameters": [6.2, 6.4, 6.5], "mean_hu": [45, 48, 50], "solid": [92, 94, 95], "morph": [0.16, 0.16, 0.18]},
        ],
    },
    {
        "patient": {"patient_code": "SYN-LN-2026-003", "name": "示例患者03", "sex": "女", "age": 49, "smoking_history": "无吸烟史", "family_history": "无", "primary_diagnosis": "Synthetic demo：右下肺纯磨玻璃结节长期稳定"},
        "nodules": [
            {"label": "主结节", "lobe": "右下叶外基底段", "nodule_type": "纯磨玻璃", "clinical_label": "稳定", "pathology_label": "未手术", "baseline_impression": "纯磨玻璃结节，形态规则", "diameters": [5.8, 5.9, 5.9], "mean_hu": [-650, -642, -638], "solid": [0, 0, 0], "morph": [0.08, 0.08, 0.08]},
        ],
    },
    {
        "patient": {"patient_code": "SYN-LN-2026-004", "name": "示例患者04", "sex": "男", "age": 71, "smoking_history": "吸烟 45 包年", "family_history": "无", "primary_diagnosis": "Synthetic demo：右上肺实性结节快速增长"},
        "nodules": [
            {"label": "主结节", "lobe": "右上叶后段", "nodule_type": "实性", "clinical_label": "恶性", "pathology_label": "浸润性腺癌", "baseline_impression": "实性结节伴毛刺和胸膜牵拉", "diameters": [7.0, 8.9, 11.7], "mean_hu": [38, 58, 82], "solid": [96, 98, 100], "morph": [0.32, 0.55, 0.78]},
        ],
    },
    {
        "patient": {"patient_code": "SYN-LN-2026-005", "name": "示例患者05", "sex": "女", "age": 62, "smoking_history": "无吸烟史", "family_history": "母亲肺癌史", "primary_diagnosis": "Synthetic demo：多发磨玻璃结节"},
        "nodules": [
            {"label": "右上叶主结节", "lobe": "右上叶前段", "nodule_type": "部分实性", "clinical_label": "进展", "pathology_label": "AIS", "baseline_impression": "磨玻璃结节内新出现小实性成分", "diameters": [6.6, 7.4, 8.2], "mean_hu": [-610, -555, -505], "solid": [5, 12, 22], "morph": [0.12, 0.2, 0.32]},
            {"label": "左上叶微结节", "lobe": "左上叶尖后段", "nodule_type": "纯磨玻璃", "clinical_label": "稳定", "pathology_label": "未手术", "baseline_impression": "微小纯磨玻璃影，稳定", "diameters": [3.6, 3.6, 3.7], "mean_hu": [-720, -718, -715], "solid": [0, 0, 0], "morph": [0.03, 0.03, 0.04]},
        ],
    },
    {
        "patient": {"patient_code": "SYN-LN-2026-006", "name": "示例患者06", "sex": "男", "age": 55, "smoking_history": "既往吸烟 15 包年", "family_history": "无", "primary_diagnosis": "Synthetic demo：钙化良性结节"},
        "nodules": [
            {"label": "主结节", "lobe": "右中叶内侧段", "nodule_type": "钙化", "clinical_label": "良性", "pathology_label": "良性", "baseline_impression": "钙化结节，考虑陈旧性肉芽肿", "diameters": [5.2, 5.1, 5.1], "mean_hu": [240, 242, 245], "solid": [100, 100, 100], "morph": [0.04, 0.04, 0.04]},
        ],
    },
    {
        "patient": {"patient_code": "SYN-LN-2026-007", "name": "示例患者07", "sex": "女", "age": 69, "smoking_history": "无吸烟史", "family_history": "姐姐肺癌史", "primary_diagnosis": "Synthetic demo：左上叶部分实性结节可疑进展"},
        "nodules": [
            {"label": "主结节", "lobe": "左上叶尖后段", "nodule_type": "部分实性", "clinical_label": "进展", "pathology_label": "MIA", "baseline_impression": "部分实性结节，密度和体积同步增加", "diameters": [9.4, 10.2, 12.1], "mean_hu": [-500, -430, -360], "solid": [22, 31, 46], "morph": [0.22, 0.35, 0.58]},
        ],
    },
    {
        "patient": {"patient_code": "SYN-LN-2026-008", "name": "示例患者08", "sex": "男", "age": 47, "smoking_history": "无吸烟史", "family_history": "无", "primary_diagnosis": "Synthetic demo：炎性结节缩小"},
        "nodules": [
            {"label": "主结节", "lobe": "右下叶后基底段", "nodule_type": "实性", "clinical_label": "缩小", "pathology_label": "良性", "baseline_impression": "实性炎性结节，抗炎后逐渐缩小", "diameters": [9.0, 7.2, 5.6], "mean_hu": [62, 48, 35], "solid": [95, 90, 88], "morph": [0.18, 0.12, 0.08]},
        ],
    },
    {
        "patient": {"patient_code": "SYN-LN-2026-009", "name": "示例患者09", "sex": "女", "age": 73, "smoking_history": "被动吸烟史", "family_history": "无", "primary_diagnosis": "Synthetic demo：多结节差异化随访"},
        "nodules": [
            {"label": "主结节", "lobe": "左下叶外基底段", "nodule_type": "部分实性", "clinical_label": "恶性", "pathology_label": "浸润性腺癌", "baseline_impression": "部分实性结节快速进展", "diameters": [10.0, 11.4, 14.2], "mean_hu": [-420, -330, -210], "solid": [35, 48, 65], "morph": [0.36, 0.52, 0.82]},
            {"label": "右肺稳定结节", "lobe": "右下叶前基底段", "nodule_type": "纯磨玻璃", "clinical_label": "稳定", "pathology_label": "未手术", "baseline_impression": "对侧纯磨玻璃结节稳定", "diameters": [4.8, 4.9, 4.9], "mean_hu": [-675, -670, -666], "solid": [0, 0, 0], "morph": [0.06, 0.06, 0.06]},
        ],
    },
    {
        "patient": {"patient_code": "SYN-LN-2026-010", "name": "示例患者10", "sex": "男", "age": 60, "smoking_history": "吸烟 20 包年", "family_history": "无", "primary_diagnosis": "Synthetic demo：中风险缓慢增长结节"},
        "nodules": [
            {"label": "主结节", "lobe": "右上叶前段", "nodule_type": "部分实性", "clinical_label": "进展", "pathology_label": "未手术", "baseline_impression": "部分实性结节缓慢增长，需短间隔复查", "diameters": [7.6, 8.0, 8.6], "mean_hu": [-560, -535, -500], "solid": [12, 16, 21], "morph": [0.1, 0.16, 0.24]},
        ],
    },
    {
        "patient": {"patient_code": "SYN-LN-2026-011", "name": "示例患者11", "sex": "女", "age": 52, "smoking_history": "无吸烟史", "family_history": "无", "primary_diagnosis": "Synthetic demo：稳定多发纯磨玻璃结节"},
        "nodules": [
            {"label": "右上叶结节", "lobe": "右上叶尖段", "nodule_type": "纯磨玻璃", "clinical_label": "稳定", "pathology_label": "未手术", "baseline_impression": "纯磨玻璃结节，三期稳定", "diameters": [6.0, 6.1, 6.1], "mean_hu": [-705, -700, -698], "solid": [0, 0, 0], "morph": [0.05, 0.05, 0.06]},
            {"label": "左下叶结节", "lobe": "左下叶后基底段", "nodule_type": "纯磨玻璃", "clinical_label": "稳定", "pathology_label": "未手术", "baseline_impression": "小纯磨玻璃结节稳定", "diameters": [4.4, 4.5, 4.5], "mean_hu": [-690, -688, -685], "solid": [0, 0, 0], "morph": [0.04, 0.04, 0.04]},
        ],
    },
    {
        "patient": {"patient_code": "SYN-LN-2026-012", "name": "示例患者12", "sex": "男", "age": 76, "smoking_history": "吸烟 50 包年", "family_history": "兄长肺癌史", "primary_diagnosis": "Synthetic demo：高危实性结节随访"},
        "nodules": [
            {"label": "主结节", "lobe": "左上叶舌段", "nodule_type": "实性", "clinical_label": "恶性", "pathology_label": "鳞癌", "baseline_impression": "高危患者实性结节增大伴分叶", "diameters": [8.8, 10.6, 13.3], "mean_hu": [55, 75, 110], "solid": [98, 100, 100], "morph": [0.28, 0.5, 0.76]},
        ],
    },
]


def _study_dates(case_index: int) -> list[date]:
    month = (case_index % 6) + 1
    return [date(2024, month, 10), date(2025, month, 14), date(2026, month, 18)]


def _volume_from_diameter(diameter: float, solid_component: float) -> float:
    return round(pi / 6 * diameter**3 * (1 + solid_component / 220), 1)


def _measurement_payload(nodule: dict[str, Any], visit_index: int) -> dict[str, Any]:
    diameter = float(nodule["diameters"][visit_index])
    mean_hu = float(nodule["mean_hu"][visit_index])
    solid = float(nodule["solid"][visit_index])
    morph = float(nodule["morph"][visit_index])
    return {
        "diameter_mm": diameter,
        "volume_mm3": _volume_from_diameter(diameter, solid),
        "mean_hu": mean_hu,
        "min_hu": mean_hu - (180 if solid < 50 else 90),
        "max_hu": mean_hu + (280 if solid < 50 else 120),
        "roi_area_mm2": round(pi * (diameter / 2) ** 2, 1),
        "solid_component_percent": solid,
        "spiculation_score": morph,
        "lobulation_score": round(morph * 0.75, 2),
        "pleural_retraction_score": round(morph * 0.55, 2),
    }


def _counts(db: Session) -> dict[str, int]:
    return {
        "patient_count": db.query(Patient).count(),
        "study_count": db.query(Study).count(),
        "nodule_count": db.query(Nodule).count(),
        "measurement_count": db.query(NoduleMeasurement).count(),
    }


def _get_or_create_patient(db: Session, payload: dict[str, Any]) -> tuple[Patient, bool]:
    patient = db.query(Patient).filter(Patient.patient_code == payload["patient_code"]).first()
    if patient:
        for key, value in payload.items():
            setattr(patient, key, value)
        return patient, False
    patient = Patient(**payload)
    db.add(patient)
    db.flush()
    return patient, True


def _get_or_create_nodule(db: Session, patient: Patient, payload: dict[str, Any]) -> tuple[Nodule, bool]:
    nodule = db.query(Nodule).filter(Nodule.patient_id == patient.id, Nodule.label == payload["label"]).first()
    fields = ["label", "lobe", "nodule_type", "clinical_label", "pathology_label", "baseline_impression"]
    if nodule:
        for key in fields:
            setattr(nodule, key, payload[key])
        return nodule, False
    nodule = Nodule(patient_id=patient.id, **{key: payload[key] for key in fields})
    db.add(nodule)
    db.flush()
    return nodule, True


def _get_or_create_study(db: Session, patient: Patient, study_date: date, visit_index: int) -> tuple[Study, bool]:
    study = db.query(Study).filter(Study.patient_id == patient.id, Study.study_date == study_date).first()
    payload = {
        "scanner": f"Synthetic demo CT-{visit_index}",
        "slice_thickness_mm": 1.0 if visit_index != 2 else 1.25,
        "series_description": "Synthetic thin-section chest CT",
        "status": "synthetic_demo",
        "file_name": f"synthetic-{patient.patient_code}-{visit_index}.zip",
    }
    if study:
        for key, value in payload.items():
            setattr(study, key, value)
        return study, False
    study = Study(patient_id=patient.id, study_date=study_date, **payload)
    db.add(study)
    db.flush()
    return study, True


def _ensure_measurement(db: Session, nodule: Nodule, study: Study, payload: dict[str, Any], seed: int) -> bool:
    measurement = db.query(NoduleMeasurement).filter(NoduleMeasurement.nodule_id == nodule.id, NoduleMeasurement.study_id == study.id).first()
    if measurement:
        for key, value in payload.items():
            setattr(measurement, key, value)
        measurement.thumbnail_seed = seed
        measurement.measurement_source = "synthetic_demo"
        return False
    db.add(NoduleMeasurement(nodule_id=nodule.id, study_id=study.id, thumbnail_seed=seed, measurement_source="synthetic_demo", **payload))
    return True


def seed_demo_data(db: Session) -> dict[str, Any]:
    before = _counts(db)
    created = {"patients_created": 0, "studies_created": 0, "nodules_created": 0, "measurements_created": 0}
    for case_index, case in enumerate(SYNTHETIC_DEMO_CASES, start=1):
        patient, patient_created = _get_or_create_patient(db, case["patient"])
        created["patients_created"] += int(patient_created)
        study_rows = []
        for visit_index, study_date in enumerate(_study_dates(case_index), start=1):
            study, study_created = _get_or_create_study(db, patient, study_date, visit_index)
            created["studies_created"] += int(study_created)
            study_rows.append(study)
        for nodule_index, nodule_payload in enumerate(case["nodules"], start=1):
            nodule, nodule_created = _get_or_create_nodule(db, patient, nodule_payload)
            created["nodules_created"] += int(nodule_created)
            for visit_index, study in enumerate(study_rows):
                measurement_created = _ensure_measurement(db, nodule, study, _measurement_payload(nodule_payload, visit_index), case_index * 100 + nodule_index * 10 + visit_index)
                created["measurements_created"] += int(measurement_created)
    db.commit()
    after = _counts(db)
    return {"synthetic": True, "case_count": len(SYNTHETIC_DEMO_CASES), **created, "before": before, "after": after}
