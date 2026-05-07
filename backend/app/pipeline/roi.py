from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pydicom


@dataclass
class RoiMeasurement:
    mean_hu: float
    min_hu: float
    max_hu: float
    roi_area_mm2: float
    solid_component_percent: float


def _first_float(value: object, default: float) -> float:
    if value is None:
        return default
    if isinstance(value, (list, tuple)):
        return float(value[0]) if value else default
    if hasattr(value, "__iter__") and not isinstance(value, (str, bytes)):
        values = list(value)
        return float(values[0]) if values else default
    return float(value)


def measure_circular_roi(dicom_path: Path, x_percent: float, y_percent: float, diameter_mm: float) -> RoiMeasurement:
    dataset = pydicom.dcmread(dicom_path, force=True)
    pixels = dataset.pixel_array.astype(np.float32)
    slope = float(getattr(dataset, "RescaleSlope", 1.0) or 1.0)
    intercept = float(getattr(dataset, "RescaleIntercept", 0.0) or 0.0)
    hu = pixels * slope + intercept

    rows, columns = hu.shape[:2]
    center_x = x_percent / 100 * (columns - 1)
    center_y = y_percent / 100 * (rows - 1)
    spacing = getattr(dataset, "PixelSpacing", [1.0, 1.0])
    row_spacing = _first_float(spacing[0] if len(spacing) > 0 else None, 1.0)
    col_spacing = _first_float(spacing[1] if len(spacing) > 1 else None, row_spacing)
    radius_x = max(diameter_mm / 2 / col_spacing, 1.0)
    radius_y = max(diameter_mm / 2 / row_spacing, 1.0)

    yy, xx = np.ogrid[:rows, :columns]
    mask = ((xx - center_x) / radius_x) ** 2 + ((yy - center_y) / radius_y) ** 2 <= 1
    roi = hu[mask]
    if roi.size == 0:
        raise ValueError("ROI contains no pixels")

    roi_area_mm2 = float(mask.sum() * row_spacing * col_spacing)
    solid_component_percent = float((roi > -160).sum() / roi.size * 100)
    return RoiMeasurement(
        mean_hu=round(float(roi.mean()), 2),
        min_hu=round(float(roi.min()), 2),
        max_hu=round(float(roi.max()), 2),
        roi_area_mm2=round(roi_area_mm2, 2),
        solid_component_percent=round(solid_component_percent, 2),
    )
