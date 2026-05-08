from __future__ import annotations

import shutil
import zipfile
from dataclasses import dataclass
from datetime import date, datetime
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any

import numpy as np
import pydicom
from PIL import Image
from pydicom.errors import InvalidDicomError


@dataclass
class RenderedSlice:
    source_path: Path
    image_path: Path
    instance_number: int
    slice_location: float | None
    rows: int
    columns: int
    window_center: float
    window_width: float


@dataclass
class DicomSeriesResult:
    metadata: dict[str, Any]
    slices: list[RenderedSlice]


def _first_value(value: Any, default: float) -> float:
    if isinstance(value, (list, tuple)):
        return float(value[0]) if value else default
    if hasattr(value, "__iter__") and not isinstance(value, (str, bytes)):
        values = list(value)
        return float(values[0]) if values else default
    if value is None:
        return default
    return float(value)


def _study_date(dataset: Any) -> date:
    raw = str(getattr(dataset, "StudyDate", ""))
    if len(raw) == 8:
        try:
            return datetime.strptime(raw, "%Y%m%d").date()
        except ValueError:
            pass
    return date.today()


def _slice_sort_key(dataset: Any) -> tuple[float, int]:
    location = getattr(dataset, "SliceLocation", None)
    instance = int(getattr(dataset, "InstanceNumber", 0) or 0)
    if location is not None:
        return (float(location), instance)
    ipp = getattr(dataset, "ImagePositionPatient", None)
    if ipp is not None and len(ipp) >= 3:
        return (float(ipp[2]), instance)
    return (float(instance), instance)


def _windowed_uint8(dataset: Any) -> np.ndarray:
    pixels = dataset.pixel_array.astype(np.float32)
    slope = float(getattr(dataset, "RescaleSlope", 1.0) or 1.0)
    intercept = float(getattr(dataset, "RescaleIntercept", 0.0) or 0.0)
    pixels = pixels * slope + intercept

    center = _first_value(getattr(dataset, "WindowCenter", None), -600.0)
    width = max(_first_value(getattr(dataset, "WindowWidth", None), 1500.0), 1.0)
    low = center - width / 2
    high = center + width / 2
    clipped = np.clip(pixels, low, high)
    return ((clipped - low) / (high - low) * 255).astype(np.uint8)


def _collect_dicom_files(input_path: Path, work_dir: Path) -> list[Path]:
    if input_path.suffix.lower() == ".zip":
        with zipfile.ZipFile(input_path) as archive:
            archive.extractall(work_dir)
        return [path for path in work_dir.rglob("*") if path.is_file()]
    return [input_path]


def _series_uid(dataset: Any) -> str:
    return str(getattr(dataset, "SeriesInstanceUID", "unknown-series"))


def _series_summary(datasets: list[tuple[Path, Any]]) -> list[dict[str, Any]]:
    groups: dict[str, list[Any]] = {}
    for _, dataset in datasets:
        groups.setdefault(_series_uid(dataset), []).append(dataset)
    summaries = []
    for uid, group in groups.items():
        first = group[0]
        summaries.append(
            {
                "series_instance_uid": uid,
                "series_description": str(getattr(first, "SeriesDescription", "DICOM CT Series"))[:128],
                "modality": str(getattr(first, "Modality", "CT")),
                "slice_count": len(group),
                "slice_thickness_mm": float(getattr(first, "SliceThickness", 1.0) or 1.0),
            }
        )
    return sorted(summaries, key=lambda item: (item["modality"] != "CT", -item["slice_count"]))


SENSITIVE_DICOM_FIELDS = ["PatientName", "PatientID", "AccessionNumber", "PatientBirthDate", "InstitutionName"]


def _anonymization_issues(dataset: Any) -> list[str]:
    return [field for field in SENSITIVE_DICOM_FIELDS if str(getattr(dataset, field, "")).strip()]


def _write_dicom_copy(dataset: Any, source: Path, target: Path, anonymize: bool) -> None:
    if not anonymize:
        shutil.copyfile(source, target)
        return
    dataset = dataset.copy()
    for field in SENSITIVE_DICOM_FIELDS:
        if hasattr(dataset, field):
            setattr(dataset, field, "ANONYMIZED")
    dataset.remove_private_tags()
    dataset.save_as(target, write_like_original=False)

def _read_dicom_datasets(input_path: Path) -> list[tuple[Path, Any]]:
    with TemporaryDirectory() as temp_name:
        candidates = _collect_dicom_files(input_path, Path(temp_name))
        datasets = []
        for candidate in candidates:
            try:
                dataset = pydicom.dcmread(candidate, force=True)
            except (InvalidDicomError, OSError):
                continue
            if hasattr(dataset, "PixelData"):
                datasets.append((candidate, dataset))
        return datasets


def inspect_dicom_series(input_path: Path) -> dict[str, Any]:
    datasets = _read_dicom_datasets(input_path)
    if not datasets:
        return {"dicom_detected": False, "series": [], "anonymization": {"checked": False, "safe": False, "unsafe_fields": []}}
    unsafe_fields = sorted({field for _, dataset in datasets for field in _anonymization_issues(dataset)})
    return {
        "dicom_detected": True,
        "series": _series_summary(datasets),
        "anonymization": {"checked": True, "safe": len(unsafe_fields) == 0, "unsafe_fields": unsafe_fields},
    }


def render_dicom_series(input_path: Path, output_dir: Path, series_uid: str | None = None, anonymize: bool = True) -> DicomSeriesResult:
    output_dir.mkdir(parents=True, exist_ok=True)
    raw_dir = output_dir / "dicom"
    png_dir = output_dir / "png"
    raw_dir.mkdir(parents=True, exist_ok=True)
    png_dir.mkdir(parents=True, exist_ok=True)

    with TemporaryDirectory() as temp_name:
        candidates = _collect_dicom_files(input_path, Path(temp_name))
        datasets = []
        for candidate in candidates:
            try:
                dataset = pydicom.dcmread(candidate, force=True)
            except (InvalidDicomError, OSError):
                continue
            if not hasattr(dataset, "PixelData"):
                continue
            if series_uid is not None and _series_uid(dataset) != series_uid:
                continue
            datasets.append((candidate, dataset))

        if not datasets:
            raise ValueError("未在上传文件中发现可解析的 DICOM 像素数据")

        datasets.sort(key=lambda item: _slice_sort_key(item[1]))
        first_dataset = datasets[0][1]
        rendered: list[RenderedSlice] = []
        for index, (source, dataset) in enumerate(datasets, start=1):
            raw_target = raw_dir / f"slice-{index:04d}.dcm"
            _write_dicom_copy(dataset, source, raw_target, anonymize)
            image_target = png_dir / f"slice-{index:04d}.png"
            image = Image.fromarray(_windowed_uint8(dataset), mode="L")
            image.save(image_target)
            rendered.append(
                RenderedSlice(
                    source_path=raw_target,
                    image_path=image_target,
                    instance_number=int(getattr(dataset, "InstanceNumber", index) or index),
                    slice_location=float(getattr(dataset, "SliceLocation")) if getattr(dataset, "SliceLocation", None) is not None else None,
                    rows=int(getattr(dataset, "Rows", image.height)),
                    columns=int(getattr(dataset, "Columns", image.width)),
                    window_center=_first_value(getattr(dataset, "WindowCenter", None), -600.0),
                    window_width=_first_value(getattr(dataset, "WindowWidth", None), 1500.0),
                )
            )

    metadata = {
        "study_date": _study_date(first_dataset),
        "scanner": str(getattr(first_dataset, "Manufacturer", "DICOM CT"))[:64],
        "slice_thickness_mm": float(getattr(first_dataset, "SliceThickness", 1.0) or 1.0),
        "series_description": str(getattr(first_dataset, "SeriesDescription", "DICOM CT Series"))[:128],
        "series_instance_uid": _series_uid(first_dataset),
        "available_series": _series_summary(datasets),
        "anonymization": {"checked": True, "safe": len(_anonymization_issues(first_dataset)) == 0, "unsafe_fields": _anonymization_issues(first_dataset), "anonymized_copy_saved": anonymize},
        "slice_count": len(rendered),
        "rows": rendered[0].rows,
        "columns": rendered[0].columns,
        "window_center": rendered[0].window_center,
        "window_width": rendered[0].window_width,
    }
    return DicomSeriesResult(metadata=metadata, slices=rendered)
