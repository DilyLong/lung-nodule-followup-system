from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models import AnalysisResult, Nodule, Patient, Study
from ..schemas import NoduleCreate, NoduleRead, PatientDetail, PatientSummary

router = APIRouter(prefix="/patients", tags=["patients"])


@router.get("", response_model=list[PatientSummary])
def list_patients(db: Session = Depends(get_db)) -> list[PatientSummary]:
    patients = (
        db.query(Patient)
        .options(joinedload(Patient.nodules), joinedload(Patient.studies), joinedload(Patient.analyses))
        .order_by(Patient.id)
        .all()
    )
    summaries: list[PatientSummary] = []
    for patient in patients:
        latest_study = max(patient.studies, key=lambda study: study.study_date, default=None)
        latest_analysis = max(patient.analyses, key=lambda analysis: analysis.created_at, default=None)
        summaries.append(
            PatientSummary(
                id=patient.id,
                patient_code=patient.patient_code,
                name=patient.name,
                sex=patient.sex,
                age=patient.age,
                smoking_history=patient.smoking_history,
                primary_diagnosis=patient.primary_diagnosis,
                nodule_type=patient.nodules[0].nodule_type if patient.nodules else None,
                latest_study_date=latest_study.study_date if latest_study else None,
                latest_risk_level=latest_analysis.risk_level if latest_analysis else None,
                latest_risk_score=latest_analysis.risk_score if latest_analysis else None,
            )
        )
    return summaries


@router.get("/{patient_id}", response_model=PatientDetail)
def get_patient(patient_id: int, db: Session = Depends(get_db)) -> Patient:
    patient = (
        db.query(Patient)
        .options(
            joinedload(Patient.studies).joinedload(Study.measurements),
            joinedload(Patient.nodules).joinedload(Nodule.measurements),
            joinedload(Patient.analyses),
        )
        .filter(Patient.id == patient_id)
        .first()
    )
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    patient.studies.sort(key=lambda study: study.study_date)
    patient.analyses.sort(key=lambda analysis: analysis.created_at)
    return patient


@router.post("/{patient_id}/nodules", response_model=NoduleRead)
def create_patient_nodule(patient_id: int, payload: NoduleCreate, db: Session = Depends(get_db)) -> Nodule:
    patient = db.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    nodule = Nodule(
        patient_id=patient_id,
        label=payload.label,
        lobe=payload.lobe,
        nodule_type=payload.nodule_type,
        clinical_label=payload.clinical_label,
        pathology_label=payload.pathology_label,
        baseline_impression=payload.baseline_impression or "由医生手动新建",
    )
    db.add(nodule)
    db.commit()
    db.refresh(nodule)
    return nodule
