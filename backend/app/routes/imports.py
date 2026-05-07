from __future__ import annotations

from fastapi import APIRouter

router = APIRouter(prefix="/imports", tags=["imports"])


@router.get("/spec")
def import_spec() -> dict:
    return {
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
