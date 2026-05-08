from pathlib import Path
from uuid import uuid4

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import ImageSlice, Patient, Study
from ..pipeline.dicom import inspect_dicom_series, render_dicom_series
from ..pipeline.preprocess import inspect_uploaded_image
from ..schemas import UploadRead

router = APIRouter(prefix="/uploads", tags=["uploads"])

UPLOAD_DIR = Path(__file__).resolve().parents[2] / "uploads"
STUDY_DATA_DIR = Path(__file__).resolve().parents[2] / "study_data"


@router.post("", response_model=UploadRead)
async def upload_study(
    patient_id: int = Form(...),
    file: UploadFile = File(...),
    series_uid: str | None = Form(default=None),
    anonymize_dicom: bool = Form(default=True),
    reject_unanonymized: bool = Form(default=False),
    db: Session = Depends(get_db),
) -> UploadRead:
    patient = db.get(Patient, patient_id)
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
    safe_name = Path(file.filename or "uploaded-study").name
    upload_id = uuid4().hex[:12]
    target = UPLOAD_DIR / f"patient-{patient_id}-{upload_id}-{safe_name}"
    content = await file.read()
    target.write_bytes(content)

    study_output_dir = STUDY_DATA_DIR / f"patient-{patient_id}-{upload_id}"
    metadata = inspect_uploaded_image(target)
    metadata = {**metadata, **inspect_dicom_series(target), "selected_series_uid": series_uid, "anonymize_dicom": anonymize_dicom, "reject_unanonymized": reject_unanonymized}
    if reject_unanonymized and metadata.get("anonymization", {}).get("safe") is False:
        target.unlink(missing_ok=True)
        unsafe_fields = "、".join(metadata.get("anonymization", {}).get("unsafe_fields", []))
        raise HTTPException(status_code=400, detail=f"DICOM 包含未脱敏字段：{unsafe_fields}")
    slices: list[ImageSlice] = []
    status = "已上传，等待真实 DICOM 解析"
    message = "文件已保存。当前文件未解析出 DICOM 像素数据，已记录文件元信息用于后续处理。"

    try:
        result = render_dicom_series(target, study_output_dir, series_uid=series_uid, anonymize=anonymize_dicom)
        metadata = {**metadata, **result.metadata, "dicom_parsed": True}
        status = "DICOM 已解析"
        message = f"DICOM 序列解析完成，已生成 {len(result.slices)} 张可浏览 CT 切片。"
    except Exception as exc:
        metadata = {**metadata, "dicom_parsed": False, "parse_error": str(exc)}
        result = None

    study = Study(
        patient_id=patient_id,
        study_date=metadata["study_date"],
        scanner=metadata["scanner"],
        slice_thickness_mm=metadata["slice_thickness_mm"],
        series_description=metadata["series_description"],
        file_name=target.name,
        status=status,
    )
    db.add(study)
    db.flush()

    if result:
        for rendered_slice in result.slices:
            image_relative_path = rendered_slice.image_path.relative_to(STUDY_DATA_DIR)
            dicom_relative_path = rendered_slice.source_path.relative_to(STUDY_DATA_DIR)
            slices.append(
                ImageSlice(
                    study_id=study.id,
                    instance_number=rendered_slice.instance_number,
                    slice_location=rendered_slice.slice_location,
                    image_path=str(image_relative_path),
                    dicom_path=str(dicom_relative_path),
                    rows=rendered_slice.rows,
                    columns=rendered_slice.columns,
                    window_center=rendered_slice.window_center,
                    window_width=rendered_slice.window_width,
                )
            )
        db.add_all(slices)

    db.commit()

    return UploadRead(
        patient_id=patient_id,
        file_name=target.name,
        message=message,
        metadata=metadata,
    )
