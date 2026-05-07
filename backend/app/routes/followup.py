from datetime import date

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Nodule, NoduleMeasurement, Patient, Study
from ..schemas import FollowupComparisonRead, FollowupPoint

router = APIRouter(prefix="/followup", tags=["followup"])


@router.get("/patients/{patient_id}", response_model=FollowupComparisonRead)
def get_patient_followup(patient_id: int, nodule_id: int | None = None, db: Session = Depends(get_db)) -> FollowupComparisonRead:
    patient = db.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    if nodule_id is not None:
        nodule = db.get(Nodule, nodule_id)
        if not nodule or nodule.patient_id != patient_id:
            raise HTTPException(status_code=404, detail="Nodule not found")
    else:
        nodule = (
            db.query(Nodule)
            .filter(Nodule.patient_id == patient_id)
            .order_by(Nodule.id)
            .first()
        )
    if not nodule:
        return FollowupComparisonRead(
            patient_id=patient_id,
            nodule_id=None,
            nodule_type=None,
            point_count=0,
            baseline_date=None,
            latest_date=None,
            diameter_change_mm=None,
            volume_change_percent=None,
            annualized_diameter_growth_mm=None,
            points=[],
        )

    rows = (
        db.query(NoduleMeasurement, Study)
        .join(Study, Study.id == NoduleMeasurement.study_id)
        .filter(NoduleMeasurement.nodule_id == nodule.id)
        .order_by(Study.study_date)
        .all()
    )
    points = [
        FollowupPoint(
            study_id=study.id,
            study_date=study.study_date,
            diameter_mm=measurement.diameter_mm,
            volume_mm3=measurement.volume_mm3,
            mean_hu=measurement.mean_hu,
            min_hu=measurement.min_hu,
            max_hu=measurement.max_hu,
            roi_area_mm2=measurement.roi_area_mm2,
            solid_component_percent=measurement.solid_component_percent,
            source="annotation" if study.file_name else "demo",
        )
        for measurement, study in rows
    ]

    diameter_change = None
    volume_change = None
    annualized_growth = None
    if len(points) >= 2:
        first = points[0]
        latest = points[-1]
        days = max((latest.study_date - first.study_date).days, 1)
        diameter_change = round(latest.diameter_mm - first.diameter_mm, 2)
        volume_change = round(((latest.volume_mm3 - first.volume_mm3) / first.volume_mm3) * 100, 2) if first.volume_mm3 else None
        annualized_growth = round(diameter_change / days * 365, 2)

    return FollowupComparisonRead(
        patient_id=patient_id,
        nodule_id=nodule.id,
        nodule_type=nodule.nodule_type,
        point_count=len(points),
        baseline_date=points[0].study_date if points else None,
        latest_date=points[-1].study_date if points else None,
        diameter_change_mm=diameter_change,
        volume_change_percent=volume_change,
        annualized_diameter_growth_mm=annualized_growth,
        points=points,
    )
