from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models import ImageSlice, Study
from ..schemas import StudyImageSeries

router = APIRouter(prefix="/imaging", tags=["imaging"])

STUDY_DATA_DIR = Path(__file__).resolve().parents[2] / "study_data"


@router.get("/studies/{study_id}", response_model=StudyImageSeries)
def get_study_image_series(study_id: int, db: Session = Depends(get_db)) -> StudyImageSeries:
    study = (
        db.query(Study)
        .options(joinedload(Study.slices))
        .filter(Study.id == study_id)
        .first()
    )
    if not study:
        raise HTTPException(status_code=404, detail="Study not found")

    slices = sorted(study.slices, key=lambda item: (item.slice_location if item.slice_location is not None else item.instance_number))
    first = slices[0] if slices else None
    return StudyImageSeries(
        study_id=study.id,
        patient_id=study.patient_id,
        study_date=study.study_date,
        series_description=study.series_description,
        slice_count=len(slices),
        rows=first.rows if first else None,
        columns=first.columns if first else None,
        window_center=first.window_center if first else None,
        window_width=first.window_width if first else None,
        slices=slices,
    )


@router.get("/registration/{preview_path:path}")
def get_registration_preview(preview_path: str) -> FileResponse:
    registration_root = (STUDY_DATA_DIR / "registration").resolve()
    image_path = (registration_root / preview_path).resolve()
    if registration_root not in image_path.parents or image_path.suffix.lower() != ".png":
        raise HTTPException(status_code=404, detail="Registration preview not found")
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Registration preview not found")
    return FileResponse(image_path, media_type="image/png")


@router.get("/slices/{slice_id}/image")
def get_slice_image(slice_id: int, db: Session = Depends(get_db)) -> FileResponse:
    image_slice = db.get(ImageSlice, slice_id)
    if not image_slice:
        raise HTTPException(status_code=404, detail="Slice not found")
    image_path = STUDY_DATA_DIR / image_slice.image_path
    if not image_path.exists():
        raise HTTPException(status_code=404, detail="Slice image file not found")
    return FileResponse(image_path, media_type="image/png")
