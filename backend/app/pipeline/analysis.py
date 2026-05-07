import json
from typing import Any

from .features import calculate_temporal_features
from .model import predict_progression_risk
from .preprocess import preprocess_patient_studies
from .recommendation import recommend_followup
from .registration import register_studies


def run_patient_analysis(patient: Any) -> dict[str, Any]:
    studies = [
        {
            "id": study.id,
            "patient_id": study.patient_id,
            "study_date": study.study_date,
            "slice_thickness_mm": study.slice_thickness_mm,
            "series_description": study.series_description,
            "slices": [
                {
                    "dicom_path": image_slice.dicom_path,
                    "image_path": image_slice.image_path,
                    "instance_number": image_slice.instance_number,
                    "slice_location": image_slice.slice_location,
                }
                for image_slice in sorted(study.slices, key=lambda item: (item.slice_location if item.slice_location is not None else item.instance_number))
            ],
        }
        for study in sorted(patient.studies, key=lambda item: item.study_date)
    ]
    if not patient.nodules:
        raise ValueError("patient has no nodule")

    nodule = patient.nodules[0]
    measurements = []
    study_by_id = {study.id: study for study in patient.studies}
    for measurement in nodule.measurements:
        study = study_by_id[measurement.study_id]
        measurements.append(
            {
                "study_id": study.id,
                "study_date": study.study_date,
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
            }
        )

    preprocessing = preprocess_patient_studies(studies)
    registration = register_studies(studies)
    features = calculate_temporal_features(measurements)
    risk = predict_progression_risk(features, nodule.nodule_type, patient.age, patient.smoking_history)
    recommendation = recommend_followup(risk, features, nodule.nodule_type)

    feature_payload = {
        "preprocessing": preprocessing,
        "registration": registration,
        "features": features,
        "risk": risk,
    }

    return {
        "risk_score": risk["risk_score"],
        "risk_level": risk["risk_level"],
        "registration_quality": registration["registration_quality"],
        "volume_doubling_time_days": features["volume_doubling_time_days"],
        "diameter_change_mm": features["diameter_change_mm"],
        "volume_change_percent": features["volume_change_percent"],
        "density_change_hu": features["density_change_hu"],
        "recommendation": recommendation,
        "features_json": json.dumps(feature_payload, ensure_ascii=False, default=str),
    }
