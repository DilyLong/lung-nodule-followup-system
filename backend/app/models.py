from datetime import date, datetime

from sqlalchemy import Date, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .database import Base


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    patient_code: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    name: Mapped[str] = mapped_column(String(64))
    sex: Mapped[str] = mapped_column(String(8))
    age: Mapped[int] = mapped_column(Integer)
    smoking_history: Mapped[str] = mapped_column(String(64))
    family_history: Mapped[str] = mapped_column(String(64), default="无")
    primary_diagnosis: Mapped[str] = mapped_column(String(128), default="肺结节随访")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    studies: Mapped[list["Study"]] = relationship(back_populates="patient", cascade="all, delete-orphan")
    nodules: Mapped[list["Nodule"]] = relationship(back_populates="patient", cascade="all, delete-orphan")
    analyses: Mapped[list["AnalysisResult"]] = relationship(back_populates="patient", cascade="all, delete-orphan")
    reports: Mapped[list["Report"]] = relationship(back_populates="patient", cascade="all, delete-orphan")


class Study(Base):
    __tablename__ = "studies"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    study_date: Mapped[date] = mapped_column(Date)
    modality: Mapped[str] = mapped_column(String(16), default="CT")
    scanner: Mapped[str] = mapped_column(String(64), default="模拟 CT")
    slice_thickness_mm: Mapped[float] = mapped_column(Float, default=1.0)
    series_description: Mapped[str] = mapped_column(String(128), default="Chest CT")
    file_name: Mapped[str | None] = mapped_column(String(256), nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="已导入")

    patient: Mapped[Patient] = relationship(back_populates="studies")
    measurements: Mapped[list["NoduleMeasurement"]] = relationship(back_populates="study", cascade="all, delete-orphan")
    slices: Mapped[list["ImageSlice"]] = relationship(back_populates="study", cascade="all, delete-orphan")


class ImageSlice(Base):
    __tablename__ = "image_slices"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    study_id: Mapped[int] = mapped_column(ForeignKey("studies.id"), index=True)
    instance_number: Mapped[int] = mapped_column(Integer, index=True)
    slice_location: Mapped[float | None] = mapped_column(Float, nullable=True)
    image_path: Mapped[str] = mapped_column(String(512))
    dicom_path: Mapped[str | None] = mapped_column(String(512), nullable=True)
    rows: Mapped[int] = mapped_column(Integer)
    columns: Mapped[int] = mapped_column(Integer)
    window_center: Mapped[float] = mapped_column(Float)
    window_width: Mapped[float] = mapped_column(Float)

    study: Mapped[Study] = relationship(back_populates="slices")
    annotations: Mapped[list["NoduleAnnotation"]] = relationship(back_populates="image_slice", cascade="all, delete-orphan")


class NoduleAnnotation(Base):
    __tablename__ = "nodule_annotations"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    study_id: Mapped[int] = mapped_column(ForeignKey("studies.id"), index=True)
    slice_id: Mapped[int] = mapped_column(ForeignKey("image_slices.id"), index=True)
    nodule_id: Mapped[int | None] = mapped_column(ForeignKey("nodules.id"), nullable=True)
    x_percent: Mapped[float] = mapped_column(Float)
    y_percent: Mapped[float] = mapped_column(Float)
    diameter_mm: Mapped[float] = mapped_column(Float)
    nodule_type: Mapped[str] = mapped_column(String(64), default="未分类")
    note: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    image_slice: Mapped[ImageSlice] = relationship(back_populates="annotations")


class Nodule(Base):
    __tablename__ = "nodules"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    label: Mapped[str] = mapped_column(String(64))
    lobe: Mapped[str] = mapped_column(String(64))
    nodule_type: Mapped[str] = mapped_column(String(64))
    baseline_impression: Mapped[str] = mapped_column(String(256))

    patient: Mapped[Patient] = relationship(back_populates="nodules")
    measurements: Mapped[list["NoduleMeasurement"]] = relationship(back_populates="nodule", cascade="all, delete-orphan")


class NoduleMeasurement(Base):
    __tablename__ = "nodule_measurements"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    nodule_id: Mapped[int] = mapped_column(ForeignKey("nodules.id"), index=True)
    study_id: Mapped[int] = mapped_column(ForeignKey("studies.id"), index=True)
    diameter_mm: Mapped[float] = mapped_column(Float)
    volume_mm3: Mapped[float] = mapped_column(Float)
    mean_hu: Mapped[float] = mapped_column(Float)
    min_hu: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_hu: Mapped[float | None] = mapped_column(Float, nullable=True)
    roi_area_mm2: Mapped[float | None] = mapped_column(Float, nullable=True)
    solid_component_percent: Mapped[float] = mapped_column(Float)
    spiculation_score: Mapped[float] = mapped_column(Float)
    lobulation_score: Mapped[float] = mapped_column(Float)
    pleural_retraction_score: Mapped[float] = mapped_column(Float)
    thumbnail_seed: Mapped[int] = mapped_column(Integer, default=1)
    measurement_source: Mapped[str] = mapped_column(String(64), default="demo")

    nodule: Mapped[Nodule] = relationship(back_populates="measurements")
    study: Mapped[Study] = relationship(back_populates="measurements")


class AnalysisResult(Base):
    __tablename__ = "analysis_results"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    nodule_id: Mapped[int | None] = mapped_column(ForeignKey("nodules.id"), nullable=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    risk_score: Mapped[float] = mapped_column(Float)
    risk_level: Mapped[str] = mapped_column(String(32))
    registration_quality: Mapped[float] = mapped_column(Float)
    volume_doubling_time_days: Mapped[float | None] = mapped_column(Float, nullable=True)
    diameter_change_mm: Mapped[float] = mapped_column(Float)
    volume_change_percent: Mapped[float] = mapped_column(Float)
    density_change_hu: Mapped[float] = mapped_column(Float)
    recommendation: Mapped[str] = mapped_column(Text)
    features_json: Mapped[str] = mapped_column(Text)

    patient: Mapped[Patient] = relationship(back_populates="analyses")


class ImportBatch(Base):
    __tablename__ = "import_batches"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    committed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    rolled_back_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    status: Mapped[str] = mapped_column(String(32), default="validated")
    qc_score: Mapped[float] = mapped_column(Float, default=0.0)
    counts_json: Mapped[str] = mapped_column(Text, default="{}")
    issues_json: Mapped[str] = mapped_column(Text, default="[]")
    message: Mapped[str] = mapped_column(Text, default="")
    operator: Mapped[str] = mapped_column(String(64), default="系统")


class ImportBatchEntity(Base):
    __tablename__ = "import_batch_entities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    batch_id: Mapped[int] = mapped_column(ForeignKey("import_batches.id"), index=True)
    entity_type: Mapped[str] = mapped_column(String(32))
    entity_id: Mapped[int] = mapped_column(Integer, index=True)
    action: Mapped[str] = mapped_column(String(32))
    stable_key: Mapped[str] = mapped_column(String(256))
    previous_json: Mapped[str | None] = mapped_column(Text, nullable=True)
    operator: Mapped[str] = mapped_column(String(64), default="系统")


class ReportVersion(Base):
    __tablename__ = "report_versions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("reports.id"), index=True)
    version_number: Mapped[int] = mapped_column(Integer)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    status: Mapped[str] = mapped_column(String(32), default="draft")
    content_markdown: Mapped[str] = mapped_column(Text)
    doctor_opinion: Mapped[str] = mapped_column(Text, default="")
    followup_plan: Mapped[str] = mapped_column(Text, default="")
    operator: Mapped[str] = mapped_column(String(64), default="系统")


class ReportAuditLog(Base):
    __tablename__ = "report_audit_logs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    report_id: Mapped[int] = mapped_column(ForeignKey("reports.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    event: Mapped[str] = mapped_column(String(64))
    message: Mapped[str] = mapped_column(Text)
    operator: Mapped[str] = mapped_column(String(64), default="系统")


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    patient_id: Mapped[int] = mapped_column(ForeignKey("patients.id"), index=True)
    analysis_id: Mapped[int] = mapped_column(ForeignKey("analysis_results.id"), index=True)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    title: Mapped[str] = mapped_column(String(128))
    content_markdown: Mapped[str] = mapped_column(Text)
    doctor_opinion: Mapped[str] = mapped_column(Text, default="")
    followup_plan: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(32), default="draft")
    finalized_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    patient: Mapped[Patient] = relationship(back_populates="reports")
