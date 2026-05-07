from datetime import date
from pathlib import Path
from typing import Any


def inspect_uploaded_image(path: Path) -> dict[str, Any]:
    suffix = path.suffix.lower()
    modality_hint = "DICOM" if suffix in {".dcm", ""} else "NIfTI" if suffix in {".nii", ".gz"} else "未知格式"
    return {
        "study_date": date.today(),
        "scanner": f"上传影像占位解析（{modality_hint}）",
        "slice_thickness_mm": 1.0,
        "series_description": "真实 DICOM/NIfTI 解析待接入",
        "file_size_bytes": path.stat().st_size,
        "file_suffix": suffix or "dicom-like",
    }


def preprocess_patient_studies(studies: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        "normalized_volume_shape": [256, 256, 192],
        "spacing_mm": [0.75, 0.75, 1.0],
        "study_count": len(studies),
        "preprocessing_status": "simulated_standardization_complete",
    }
