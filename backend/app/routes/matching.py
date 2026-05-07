from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import Nodule, NoduleAnnotation, NoduleMeasurement, Study
from ..schemas import MatchCandidateRead, NoduleAnnotationRead

router = APIRouter(prefix="/matching", tags=["matching"])


def _latest_measurement(nodule_id: int, db: Session) -> tuple[NoduleMeasurement | None, Study | None]:
    row = (
        db.query(NoduleMeasurement, Study)
        .join(Study, Study.id == NoduleMeasurement.study_id)
        .filter(NoduleMeasurement.nodule_id == nodule_id)
        .order_by(Study.study_date.desc())
        .first()
    )
    if not row:
        return None, None
    return row


def _score_candidate(annotation: NoduleAnnotation, nodule: Nodule, measurement: NoduleMeasurement | None) -> tuple[float, str]:
    score = 0.2
    reasons: list[str] = []
    if annotation.nodule_type == nodule.nodule_type:
        score += 0.3
        reasons.append("类型一致")
    elif annotation.nodule_type in nodule.nodule_type or nodule.nodule_type in annotation.nodule_type:
        score += 0.18
        reasons.append("类型相近")
    if measurement:
        diff = abs(annotation.diameter_mm - measurement.diameter_mm)
        if diff <= 2:
            score += 0.3
            reasons.append(f"直径接近，差 {diff:.1f} mm")
        elif diff <= 5:
            score += 0.18
            reasons.append(f"直径变化可接受，差 {diff:.1f} mm")
        else:
            score += 0.05
            reasons.append(f"直径差较大，差 {diff:.1f} mm")
    else:
        score += 0.08
        reasons.append("暂无既往测量")
    if annotation.note and nodule.lobe in annotation.note:
        score += 0.12
        reasons.append("备注肺叶匹配")
    return round(min(score, 0.98), 2), "；".join(reasons) or "候选结节"


@router.get("/annotations/{annotation_id}/candidates", response_model=list[MatchCandidateRead])
def list_match_candidates(annotation_id: int, db: Session = Depends(get_db)) -> list[MatchCandidateRead]:
    annotation = db.get(NoduleAnnotation, annotation_id)
    if not annotation:
        raise HTTPException(status_code=404, detail="Annotation not found")

    nodules = (
        db.query(Nodule)
        .filter(Nodule.patient_id == annotation.patient_id)
        .order_by(Nodule.id)
        .all()
    )
    candidates: list[MatchCandidateRead] = []
    for nodule in nodules:
        latest_measurement, latest_study = _latest_measurement(nodule.id, db)
        score, reason = _score_candidate(annotation, nodule, latest_measurement)
        candidates.append(
            MatchCandidateRead(
                nodule_id=nodule.id,
                label=nodule.label,
                lobe=nodule.lobe,
                nodule_type=nodule.nodule_type,
                latest_diameter_mm=latest_measurement.diameter_mm if latest_measurement else None,
                latest_study_date=latest_study.study_date if latest_study else None,
                score=score,
                reason=reason,
            )
        )
    return sorted(candidates, key=lambda item: item.score, reverse=True)


@router.post("/annotations/{annotation_id}/confirm", response_model=NoduleAnnotationRead)
def confirm_annotation_match(annotation_id: int, nodule_id: int, db: Session = Depends(get_db)) -> NoduleAnnotation:
    annotation = db.get(NoduleAnnotation, annotation_id)
    if not annotation:
        raise HTTPException(status_code=404, detail="Annotation not found")
    nodule = db.get(Nodule, nodule_id)
    if not nodule or nodule.patient_id != annotation.patient_id:
        raise HTTPException(status_code=400, detail="Nodule must belong to the same patient")
    annotation.nodule_id = nodule.id
    db.commit()
    db.refresh(annotation)
    return annotation
