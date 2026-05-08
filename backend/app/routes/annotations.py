from math import pi
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ImageSlice, Nodule, NoduleAnnotation, NoduleMeasurement, Patient, Study
from ..pipeline.roi import measure_circular_roi
from ..schemas import AnnotationMeasurementRead, NoduleAnnotationCreate, NoduleAnnotationRead, NoduleAnnotationUpdate

router = APIRouter(prefix="/annotations", tags=["annotations"])


@router.get("/studies/{study_id}", response_model=list[NoduleAnnotationRead])
def list_study_annotations(study_id: int, db: Session = Depends(get_db)) -> list[NoduleAnnotation]:
    study = db.get(Study, study_id)
    if not study:
        raise HTTPException(status_code=404, detail="Study not found")
    return (
        db.query(NoduleAnnotation)
        .filter(NoduleAnnotation.study_id == study_id)
        .order_by(NoduleAnnotation.created_at.desc())
        .all()
    )


@router.post("", response_model=NoduleAnnotationRead)
def create_annotation(payload: NoduleAnnotationCreate, db: Session = Depends(get_db)) -> NoduleAnnotation:
    patient = db.get(Patient, payload.patient_id)
    study = db.get(Study, payload.study_id)
    image_slice = db.get(ImageSlice, payload.slice_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    if not study:
        raise HTTPException(status_code=404, detail="Study not found")
    if not image_slice:
        raise HTTPException(status_code=404, detail="Slice not found")
    if study.patient_id != patient.id or image_slice.study_id != study.id:
        raise HTTPException(status_code=400, detail="Annotation patient/study/slice mismatch")
    if not 0 <= payload.x_percent <= 100 or not 0 <= payload.y_percent <= 100:
        raise HTTPException(status_code=400, detail="Annotation coordinates must be 0-100 percent")
    if payload.diameter_mm <= 0:
        raise HTTPException(status_code=400, detail="Nodule diameter must be positive")

    if payload.nodule_id:
        nodule = db.get(Nodule, payload.nodule_id)
        if not nodule or nodule.patient_id != patient.id:
            raise HTTPException(status_code=400, detail="Annotation nodule must belong to patient")
    annotation = NoduleAnnotation(**payload.model_dump())
    db.add(annotation)
    db.commit()
    db.refresh(annotation)
    return annotation




def _get_or_create_primary_nodule(patient: Patient, annotation: NoduleAnnotation, db: Session) -> Nodule:
    if annotation.nodule_id:
        nodule = db.get(Nodule, annotation.nodule_id)
        if nodule and nodule.patient_id == patient.id:
            return nodule
    nodule = (
        db.query(Nodule)
        .filter(Nodule.patient_id == patient.id)
        .order_by(Nodule.id)
        .first()
    )
    if nodule:
        return nodule
    nodule = Nodule(
        patient_id=patient.id,
        label="主结节",
        lobe="待医生确认",
        nodule_type=annotation.nodule_type,
        baseline_impression="由 DICOM 切片手动标注生成",
    )
    db.add(nodule)
    db.flush()
    return nodule


def _estimated_volume(diameter_mm: float) -> float:
    radius = diameter_mm / 2
    return round(4 / 3 * pi * radius ** 3, 2)


@router.post("/{annotation_id}/measurement", response_model=AnnotationMeasurementRead)
def create_measurement_from_annotation(annotation_id: int, db: Session = Depends(get_db)) -> AnnotationMeasurementRead:
    annotation = db.get(NoduleAnnotation, annotation_id)
    if not annotation:
        raise HTTPException(status_code=404, detail="Annotation not found")
    patient = db.get(Patient, annotation.patient_id)
    study = db.get(Study, annotation.study_id)
    if not patient or not study:
        raise HTTPException(status_code=404, detail="Patient or study not found")

    image_slice = db.get(ImageSlice, annotation.slice_id)
    nodule = _get_or_create_primary_nodule(patient, annotation, db)
    existing = (
        db.query(NoduleMeasurement)
        .filter(NoduleMeasurement.nodule_id == nodule.id, NoduleMeasurement.study_id == study.id)
        .first()
    )
    if existing:
        measurement = existing
        message = "已更新该检查的主结节随访测量。"
    else:
        measurement = NoduleMeasurement(nodule_id=nodule.id, study_id=study.id, thumbnail_seed=study.id, measurement_source="manual_annotation")
        db.add(measurement)
        message = "已从标注生成主结节随访测量。"

    roi_measurement = None
    if image_slice and image_slice.dicom_path:
        dicom_path = Path(__file__).resolve().parents[2] / "study_data" / image_slice.dicom_path
        roi_measurement = measure_circular_roi(
            dicom_path,
            annotation.x_percent,
            annotation.y_percent,
            annotation.diameter_mm,
        )

    measurement.diameter_mm = annotation.diameter_mm
    measurement.volume_mm3 = _estimated_volume(annotation.diameter_mm)
    if roi_measurement:
        measurement.mean_hu = roi_measurement.mean_hu
        measurement.min_hu = roi_measurement.min_hu
        measurement.max_hu = roi_measurement.max_hu
        measurement.roi_area_mm2 = roi_measurement.roi_area_mm2
        measurement.solid_component_percent = roi_measurement.solid_component_percent
    else:
        measurement.mean_hu = -600.0 if "磨玻璃" in annotation.nodule_type else 40.0
        measurement.min_hu = None
        measurement.max_hu = None
        measurement.roi_area_mm2 = None
        measurement.solid_component_percent = 30.0 if "混合" in annotation.nodule_type else 95.0 if "实性" in annotation.nodule_type else 0.0
    measurement.spiculation_score = 0.0
    measurement.lobulation_score = 0.0
    measurement.pleural_retraction_score = 0.0
    annotation.nodule_id = nodule.id
    measurement.measurement_source = "roi_dicom" if roi_measurement else "manual_annotation"

    db.commit()
    db.refresh(annotation)
    db.refresh(measurement)
    db.refresh(nodule)
    return AnnotationMeasurementRead(annotation=annotation, measurement=measurement, nodule=nodule, message=message)


@router.put("/{annotation_id}", response_model=NoduleAnnotationRead)
def update_annotation(annotation_id: int, payload: NoduleAnnotationUpdate, db: Session = Depends(get_db)) -> NoduleAnnotation:
    annotation = db.get(NoduleAnnotation, annotation_id)
    if not annotation:
        raise HTTPException(status_code=404, detail="Annotation not found")
    if payload.nodule_id is not None:
        nodule = db.get(Nodule, payload.nodule_id)
        if not nodule or nodule.patient_id != annotation.patient_id:
            raise HTTPException(status_code=400, detail="Annotation nodule must belong to patient")
    if not 0 <= payload.x_percent <= 100 or not 0 <= payload.y_percent <= 100:
        raise HTTPException(status_code=400, detail="Annotation coordinates must be 0-100 percent")
    if payload.diameter_mm <= 0:
        raise HTTPException(status_code=400, detail="Nodule diameter must be positive")
    annotation.nodule_id = payload.nodule_id
    annotation.x_percent = payload.x_percent
    annotation.y_percent = payload.y_percent
    annotation.diameter_mm = payload.diameter_mm
    annotation.nodule_type = payload.nodule_type
    annotation.note = payload.note
    db.commit()
    db.refresh(annotation)
    return annotation


@router.delete("/{annotation_id}")
def delete_annotation(annotation_id: int, db: Session = Depends(get_db)) -> dict[str, str]:
    annotation = db.get(NoduleAnnotation, annotation_id)
    if not annotation:
        raise HTTPException(status_code=404, detail="Annotation not found")
    db.delete(annotation)
    db.commit()
    return {"status": "deleted"}
