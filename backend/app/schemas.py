from datetime import date, datetime
from typing import Any

from pydantic import BaseModel, ConfigDict


class MeasurementRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    nodule_id: int
    study_id: int
    diameter_mm: float
    volume_mm3: float
    mean_hu: float
    min_hu: float | None = None
    max_hu: float | None = None
    roi_area_mm2: float | None = None
    solid_component_percent: float
    spiculation_score: float
    lobulation_score: float
    pleural_retraction_score: float
    thumbnail_seed: int


class ImageSliceRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    study_id: int
    instance_number: int
    slice_location: float | None
    image_path: str
    dicom_path: str | None = None
    rows: int
    columns: int
    window_center: float
    window_width: float


class StudyRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    study_date: date
    modality: str
    scanner: str
    slice_thickness_mm: float
    series_description: str
    file_name: str | None
    status: str
    measurements: list[MeasurementRead] = []
    slices: list[ImageSliceRead] = []


class NoduleCreate(BaseModel):
    label: str
    lobe: str
    nodule_type: str
    baseline_impression: str = ""


class NoduleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    label: str
    lobe: str
    nodule_type: str
    baseline_impression: str
    measurements: list[MeasurementRead] = []


class AnalysisRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    nodule_id: int | None = None
    created_at: datetime
    risk_score: float
    risk_level: str
    registration_quality: float
    volume_doubling_time_days: float | None
    diameter_change_mm: float
    volume_change_percent: float
    density_change_hu: float
    recommendation: str
    features_json: str


class PatientSummary(BaseModel):
    id: int
    patient_code: str
    name: str
    sex: str
    age: int
    smoking_history: str
    primary_diagnosis: str
    nodule_type: str | None
    latest_study_date: date | None
    latest_risk_level: str | None
    latest_risk_score: float | None


class PatientDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_code: str
    name: str
    sex: str
    age: int
    smoking_history: str
    family_history: str
    primary_diagnosis: str
    studies: list[StudyRead]
    nodules: list[NoduleRead]
    analyses: list[AnalysisRead]


class AnalysisRequest(BaseModel):
    patient_id: int


class ReportRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    analysis_id: int
    created_at: datetime
    title: str
    content_markdown: str
    doctor_opinion: str = ""
    followup_plan: str = ""
    status: str = "draft"
    finalized_at: datetime | None = None


class ReportUpdate(BaseModel):
    content_markdown: str
    doctor_opinion: str = ""
    followup_plan: str = ""
    status: str = "draft"


class NoduleAnnotationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    patient_id: int
    study_id: int
    slice_id: int
    nodule_id: int | None = None
    x_percent: float
    y_percent: float
    diameter_mm: float
    nodule_type: str
    note: str
    created_at: datetime


class NoduleAnnotationCreate(BaseModel):
    patient_id: int
    study_id: int
    slice_id: int
    nodule_id: int | None = None
    x_percent: float
    y_percent: float
    diameter_mm: float
    nodule_type: str = "未分类"
    note: str = ""


class AnnotationMeasurementRead(BaseModel):
    annotation: NoduleAnnotationRead
    measurement: MeasurementRead
    nodule: NoduleRead
    message: str


class FollowupPoint(BaseModel):
    study_id: int
    study_date: date
    diameter_mm: float
    volume_mm3: float
    mean_hu: float
    min_hu: float | None = None
    max_hu: float | None = None
    roi_area_mm2: float | None = None
    solid_component_percent: float
    source: str


class FollowupComparisonRead(BaseModel):
    patient_id: int
    nodule_id: int | None
    nodule_type: str | None
    point_count: int
    baseline_date: date | None
    latest_date: date | None
    diameter_change_mm: float | None
    volume_change_percent: float | None
    annualized_diameter_growth_mm: float | None
    points: list[FollowupPoint]


class MatchCandidateRead(BaseModel):
    nodule_id: int
    label: str
    lobe: str
    nodule_type: str
    latest_diameter_mm: float | None
    latest_study_date: date | None
    score: float
    reason: str


class StudyImageSeries(BaseModel):
    study_id: int
    patient_id: int
    study_date: date
    series_description: str
    slice_count: int
    rows: int | None
    columns: int | None
    window_center: float | None
    window_width: float | None
    slices: list[ImageSliceRead]




class UploadRead(BaseModel):
    patient_id: int
    file_name: str
    message: str
    metadata: dict[str, Any]


class ImportValidationIssue(BaseModel):
    file: str
    row: int | None = None
    column: str | None = None
    severity: str
    message: str


class ImportFileValidationSummary(BaseModel):
    file: str
    row_count: int
    missing_required_columns: list[str] = []
    unknown_columns: list[str] = []


class ImportValidationSummary(BaseModel):
    file_count: int
    total_rows: int
    error_count: int
    warning_count: int


class ImportValidationReport(BaseModel):
    valid: bool
    summary: ImportValidationSummary
    files: list[ImportFileValidationSummary]
    issues: list[ImportValidationIssue]


class ImportCommitCounts(BaseModel):
    patients_created: int = 0
    patients_updated: int = 0
    studies_created: int = 0
    studies_updated: int = 0
    nodules_created: int = 0
    nodules_updated: int = 0
    measurements_created: int = 0
    measurements_updated: int = 0


class ImportCommitReport(BaseModel):
    committed: bool
    validation: ImportValidationReport
    counts: ImportCommitCounts
    patient_ids: list[int] = []
    message: str


class ModelSelfCheckIssue(BaseModel):
    field: str
    severity: str
    message: str


class ModelSelfCheckCheck(BaseModel):
    name: str
    passed: bool
    message: str


class ModelSelfCheckReport(BaseModel):
    passed: bool
    mode: str
    backend: str
    demo_input_source: str
    checks: list[ModelSelfCheckCheck]
    issues: list[ModelSelfCheckIssue]
    model_input_preview: dict[str, Any]
    inference: dict[str, Any] | None
    runtime_status: dict[str, Any]
