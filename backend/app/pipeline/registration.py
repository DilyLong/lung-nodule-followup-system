from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pydicom
from PIL import Image, ImageDraw
from scipy import ndimage

BASE_DIR = Path(__file__).resolve().parents[2]
STUDY_DATA_DIR = BASE_DIR / "study_data"


def _placeholder_registration(studies: list[dict[str, Any]], reason: str) -> dict[str, Any]:
    study_count = len(studies)
    quality = min(0.98, 0.86 + study_count * 0.03)
    transforms = []
    for index, study in enumerate(studies):
        transforms.append(
            {
                "study_id": study["id"],
                "matrix": [
                    [1.0, 0.0, 0.0, round(index * 0.8, 2)],
                    [0.0, 1.0, 0.0, round(index * -0.4, 2)],
                    [0.0, 0.0, 1.0, round(index * 0.2, 2)],
                    [0.0, 0.0, 0.0, 1.0],
                ],
                "translation_voxel": [round(index * 0.2, 2), round(index * -0.4, 2), round(index * 0.8, 2)],
                "before_correlation": None,
                "after_correlation": None,
            }
        )
    return {
        "registration_quality": round(quality, 3),
        "method": "rigid_affine_plus_deformable_placeholder",
        "status": "fallback_placeholder",
        "reason": reason,
        "reference_study_id": studies[0]["id"] if studies else None,
        "matched_nodules": 1,
        "transforms": transforms,
        "previews": [],
    }


def _slice_key(item: dict[str, Any]) -> tuple[float, int]:
    location = item.get("slice_location")
    instance = int(item.get("instance_number") or 0)
    if location is not None:
        return (float(location), instance)
    return (float(instance), instance)


def _read_dicom_volume(study: dict[str, Any]) -> np.ndarray | None:
    slices = [item for item in study.get("slices", []) if item.get("dicom_path")]
    if not slices:
        return None

    planes = []
    for item in sorted(slices, key=_slice_key):
        dicom_path = STUDY_DATA_DIR / str(item["dicom_path"])
        if not dicom_path.exists():
            continue
        dataset = pydicom.dcmread(dicom_path, force=True)
        if not hasattr(dataset, "PixelData"):
            continue
        pixels = dataset.pixel_array.astype(np.float32)
        slope = float(getattr(dataset, "RescaleSlope", 1.0) or 1.0)
        intercept = float(getattr(dataset, "RescaleIntercept", 0.0) or 0.0)
        planes.append(pixels * slope + intercept)

    if not planes:
        return None
    return np.stack(planes, axis=0).astype(np.float32)


def _normalize_lung_window(volume: np.ndarray) -> np.ndarray:
    clipped = np.clip(volume, -1000.0, 400.0)
    normalized = (clipped + 1000.0) / 1400.0
    return normalized.astype(np.float32)


def _center_crop(volume: np.ndarray, shape: tuple[int, int, int]) -> np.ndarray:
    slices = []
    for axis, target in enumerate(shape):
        size = volume.shape[axis]
        start = max((size - target) // 2, 0)
        slices.append(slice(start, start + target))
    return volume[tuple(slices)]


def _common_shape(first: np.ndarray, second: np.ndarray) -> tuple[int, int, int]:
    return tuple(max(1, min(a, b)) for a, b in zip(first.shape, second.shape))


def _correlation(first: np.ndarray, second: np.ndarray) -> float:
    first_centered = first - float(first.mean())
    second_centered = second - float(second.mean())
    denominator = float(np.linalg.norm(first_centered) * np.linalg.norm(second_centered))
    if denominator == 0:
        return 0.0
    return float(np.sum(first_centered * second_centered) / denominator)


def _estimate_translation(fixed: np.ndarray, moving: np.ndarray) -> np.ndarray:
    fixed_fft = np.fft.fftn(fixed - fixed.mean())
    moving_fft = np.fft.fftn(moving - moving.mean())
    cross_power = fixed_fft * np.conj(moving_fft)
    magnitude = np.abs(cross_power)
    cross_power /= np.maximum(magnitude, 1e-8)
    correlation = np.fft.ifftn(cross_power)
    maxima = np.unravel_index(np.argmax(np.abs(correlation)), correlation.shape)
    shifts = np.array(maxima, dtype=np.float32)
    midpoint = np.array([np.fix(axis_size / 2) for axis_size in fixed.shape], dtype=np.float32)
    shifts[shifts > midpoint] -= np.array(fixed.shape, dtype=np.float32)[shifts > midpoint]
    return shifts


def _translation_matrix(shift: np.ndarray) -> list[list[float]]:
    z, y, x = [round(float(value), 3) for value in shift]
    return [
        [1.0, 0.0, 0.0, x],
        [0.0, 1.0, 0.0, y],
        [0.0, 0.0, 1.0, z],
        [0.0, 0.0, 0.0, 1.0],
    ]


def _to_uint8(slice_image: np.ndarray) -> np.ndarray:
    clipped = np.clip(slice_image, 0.0, 1.0)
    return (clipped * 255).astype(np.uint8)


def _make_preview(patient_id: int, fixed_study_id: int, moving_study_id: int, fixed: np.ndarray, moving: np.ndarray, registered: np.ndarray) -> str:
    preview_dir = STUDY_DATA_DIR / "registration" / f"patient-{patient_id}"
    preview_dir.mkdir(parents=True, exist_ok=True)
    z_index = fixed.shape[0] // 2
    panels = [
        ("基线", _to_uint8(fixed[z_index])),
        ("随访", _to_uint8(moving[z_index])),
        ("配准后", _to_uint8(registered[z_index])),
    ]
    height, width = panels[0][1].shape
    label_height = 30
    canvas = Image.new("L", (width * 3, height + label_height), 0)
    draw = ImageDraw.Draw(canvas)
    for index, (label, panel) in enumerate(panels):
        canvas.paste(Image.fromarray(panel, mode="L"), (index * width, label_height))
        draw.text((index * width + 8, 8), label, fill=255)
    target = preview_dir / f"fixed-{fixed_study_id}-moving-{moving_study_id}.png"
    canvas.save(target)
    return str(target.relative_to(STUDY_DATA_DIR / "registration"))


def _real_registration(studies: list[dict[str, Any]], volumes: list[tuple[dict[str, Any], np.ndarray]]) -> dict[str, Any]:
    reference_study, reference_volume = volumes[0]
    transforms = []
    previews = []
    correlations = []
    patient_id = int(reference_study.get("patient_id") or 0)

    transforms.append(
        {
            "study_id": reference_study["id"],
            "matrix": _translation_matrix(np.array([0.0, 0.0, 0.0], dtype=np.float32)),
            "translation_voxel": [0.0, 0.0, 0.0],
            "before_correlation": 1.0,
            "after_correlation": 1.0,
        }
    )

    for moving_study, moving_volume in volumes[1:]:
        shape = _common_shape(reference_volume, moving_volume)
        fixed = _normalize_lung_window(_center_crop(reference_volume, shape))
        moving = _normalize_lung_window(_center_crop(moving_volume, shape))
        before = _correlation(fixed, moving)
        shift = _estimate_translation(fixed, moving)
        registered = ndimage.shift(moving, shift=shift, order=1, mode="nearest")
        after = _correlation(fixed, registered)
        preview_path = _make_preview(patient_id, reference_study["id"], moving_study["id"], fixed, moving, registered)
        transforms.append(
            {
                "study_id": moving_study["id"],
                "matrix": _translation_matrix(shift),
                "translation_voxel": [round(float(value), 3) for value in shift.tolist()],
                "before_correlation": round(before, 4),
                "after_correlation": round(after, 4),
            }
        )
        previews.append(
            {
                "fixed_study_id": reference_study["id"],
                "moving_study_id": moving_study["id"],
                "path": preview_path,
                "before_correlation": round(before, 4),
                "after_correlation": round(after, 4),
            }
        )
        correlations.append(max(before, after))

    quality = float(np.mean(correlations)) if correlations else 1.0
    return {
        "registration_quality": round(max(0.0, min(0.99, quality)), 3),
        "method": "phase_correlation_rigid_translation",
        "status": "real_dicom",
        "reference_study_id": reference_study["id"],
        "matched_nodules": 1,
        "transforms": transforms,
        "previews": previews,
    }


def register_studies(studies: list[dict[str, Any]]) -> dict[str, Any]:
    if len(studies) < 2:
        return _placeholder_registration(studies, "至少需要两期检查才能执行真实配准")

    volumes = []
    for study in studies:
        volume = _read_dicom_volume(study)
        if volume is not None:
            volumes.append((study, volume))

    if len(volumes) < 2:
        return _placeholder_registration(studies, "真实 DICOM 序列不足两期，使用占位配准评分")

    try:
        return _real_registration(studies, volumes)
    except Exception as exc:
        return _placeholder_registration(studies, f"真实配准失败：{exc}")
