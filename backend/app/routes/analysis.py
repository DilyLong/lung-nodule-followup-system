import json

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models import AnalysisResult, Nodule, Patient, Study
from ..pipeline.analysis import run_patient_analysis
from ..schemas import AnalysisRead

router = APIRouter(prefix="/analysis", tags=["analysis"])


@router.post("/{patient_id}/run", response_model=AnalysisRead)
def run_analysis(patient_id: int, nodule_id: int | None = None, db: Session = Depends(get_db)) -> AnalysisResult:
    patient = (
        db.query(Patient)
        .options(
            joinedload(Patient.studies).joinedload(Study.measurements),
            joinedload(Patient.studies).joinedload(Study.slices),
            joinedload(Patient.nodules).joinedload(Nodule.measurements),
        )
        .filter(Patient.id == patient_id)
        .first()
    )
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")
    if len(patient.studies) < 2:
        raise HTTPException(status_code=400, detail="At least two CT studies are required for temporal analysis")

    try:
        result = run_patient_analysis(patient, nodule_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    analysis = AnalysisResult(patient_id=patient.id, **result)
    db.add(analysis)
    db.commit()
    db.refresh(analysis)
    return analysis


@router.get("/{patient_id}/latest", response_model=AnalysisRead | None)
def latest_analysis(patient_id: int, nodule_id: int | None = None, db: Session = Depends(get_db)) -> AnalysisResult | None:
    query = db.query(AnalysisResult).filter(AnalysisResult.patient_id == patient_id)
    if nodule_id is not None:
        query = query.filter(AnalysisResult.nodule_id == nodule_id)
    return query.order_by(AnalysisResult.created_at.desc()).first()


@router.get("/{analysis_id}/features")
def get_analysis_features(analysis_id: int, db: Session = Depends(get_db)) -> dict:
    analysis = db.get(AnalysisResult, analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")
    return json.loads(analysis.features_json)
