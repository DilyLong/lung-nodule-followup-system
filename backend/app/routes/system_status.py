from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AnalysisResult, ImportBatch, Nodule, NoduleMeasurement, Patient, Report, Study
from ..pipeline.model import model_runtime_status
from ..pipeline.training import training_readiness

router = APIRouter(prefix="/system", tags=["system"])


def _latest_analysis(db: Session) -> dict[str, Any] | None:
    analysis = db.query(AnalysisResult).order_by(AnalysisResult.created_at.desc()).first()
    if not analysis:
        return None
    return {
        "id": analysis.id,
        "patient_id": analysis.patient_id,
        "nodule_id": analysis.nodule_id,
        "created_at": analysis.created_at,
        "risk_level": analysis.risk_level,
        "risk_score": analysis.risk_score,
    }


def _latest_report(db: Session, final_only: bool = False) -> dict[str, Any] | None:
    query = db.query(Report)
    if final_only:
        query = query.filter(Report.status == "final")
    report = query.order_by(Report.created_at.desc()).first()
    if not report:
        return None
    return {
        "id": report.id,
        "patient_id": report.patient_id,
        "analysis_id": report.analysis_id,
        "created_at": report.created_at,
        "status": report.status,
        "finalized_at": report.finalized_at,
    }


def _actions(model_status: dict[str, Any], analysis_count: int, final_report_count: int, real_dicom_count: int) -> list[dict[str, Any]]:
    actions = [
        {
            "key": "import_csv",
            "severity": "info",
            "title": "导入真实队列 CSV",
            "description": "校验、预览并确认后可将 patients/studies/nodules/measurements 写入数据库，导入批次支持审计和回滚。",
            "target_page": "upload",
        }
    ]
    if real_dicom_count == 0:
        actions.append(
            {
                "key": "upload_dicom",
                "severity": "warning",
                "title": "上传真实 DICOM 序列",
                "description": "当前还没有解析成功的真实 DICOM 切片，建议上传 zip 序列后完成标注和 ROI 测量。",
                "target_page": "upload",
            }
        )
    if analysis_count == 0:
        actions.append(
            {
                "key": "run_analysis",
                "severity": "warning",
                "title": "运行目标结节分析",
                "description": "选择病例和目标结节后运行时序分析，生成风险评分和随访建议。",
                "target_page": "dashboard",
            }
        )
    if final_report_count == 0:
        actions.append(
            {
                "key": "finalize_report",
                "severity": "info",
                "title": "确认最终版报告",
                "description": "生成结构化报告后填写医生意见并确认最终版，便于临床归档和导出。",
                "target_page": "dashboard",
            }
        )
    if not str(model_status.get("active_mode", "")).startswith("real_"):
        actions.append(
            {
                "key": "model_self_check",
                "severity": "info",
                "title": "接入并自检真实模型",
                "description": "放入 temporal_model.pt 或 temporal_model.onnx 后，在模型状态页运行 dry-run 自检。",
                "target_page": "modelStatus",
            }
        )
    return actions


def _latest_import_batch(db: Session) -> dict[str, Any] | None:
    batch = db.query(ImportBatch).order_by(ImportBatch.created_at.desc()).first()
    if not batch:
        return None
    return {
        "id": batch.id,
        "created_at": batch.created_at,
        "status": batch.status,
        "qc_score": batch.qc_score,
        "message": batch.message,
    }


def _measurement_sources(db: Session) -> dict[str, int]:
    rows = db.query(NoduleMeasurement.measurement_source).all()
    counts: dict[str, int] = {}
    for (source,) in rows:
        counts[source or "unknown"] = counts.get(source or "unknown", 0) + 1
    return counts


def _data_quality(db: Session) -> dict[str, Any]:
    nodules = db.query(Nodule).all()
    measurements = db.query(NoduleMeasurement).all()
    studies = db.query(Study).all()
    label_counts: dict[str, int] = {}
    pathology_counts: dict[str, int] = {}
    for nodule in nodules:
        label_counts[nodule.clinical_label or "未填写"] = label_counts.get(nodule.clinical_label or "未填写", 0) + 1
        pathology_counts[nodule.pathology_label or "未填写"] = pathology_counts.get(nodule.pathology_label or "未填写", 0) + 1
    missing = {
        "clinical_label": sum(1 for nodule in nodules if not nodule.clinical_label or nodule.clinical_label == "待定"),
        "pathology_label": sum(1 for nodule in nodules if not nodule.pathology_label),
        "volume_mm3": sum(1 for item in measurements if item.volume_mm3 is None or item.volume_mm3 <= 0),
        "mean_hu": sum(1 for item in measurements if item.mean_hu is None),
        "roi_area_mm2": sum(1 for item in measurements if item.roi_area_mm2 is None),
        "dicom_slices": sum(1 for study in studies if len(study.slices) == 0),
    }
    followup_intervals = []
    for patient in db.query(Patient).all():
        ordered = sorted(patient.studies, key=lambda item: item.study_date)
        for index in range(1, len(ordered)):
            followup_intervals.append((ordered[index].study_date - ordered[index - 1].study_date).days)
    readiness = training_readiness(db)
    return {
        "label_distribution": label_counts,
        "pathology_distribution": pathology_counts,
        "missing_fields": missing,
        "followup_interval_days": {
            "count": len(followup_intervals),
            "min": min(followup_intervals) if followup_intervals else None,
            "median": sorted(followup_intervals)[len(followup_intervals) // 2] if followup_intervals else None,
            "max": max(followup_intervals) if followup_intervals else None,
        },
        "training_readiness": {
            "ready": readiness["ready"],
            "eligible_sample_count": readiness["eligible_sample_count"],
            "positive_count": readiness["positive_count"],
            "negative_count": readiness["negative_count"],
            "excluded_count": readiness["excluded_count"],
            "top_exclusions": readiness["exclusions"][:8],
        },
    }


@router.get("/status")
def get_system_status(db: Session = Depends(get_db)) -> dict[str, Any]:
    model_status = model_runtime_status()
    final_report_count = db.query(Report).filter(Report.status == "final").count()
    analysis_count = db.query(AnalysisResult).count()
    real_dicom_count = db.query(Study).filter(Study.status == "DICOM 已解析").count()
    return {
        "backend": {
            "status": "ok",
            "api_version": "0.1.0",
            "checked_at": datetime.now(timezone.utc).isoformat(),
        },
        "database": {
            "patient_count": db.query(Patient).count(),
            "study_count": db.query(Study).count(),
            "nodule_count": db.query(Nodule).count(),
            "measurement_count": db.query(NoduleMeasurement).count(),
            "analysis_count": analysis_count,
            "report_count": db.query(Report).count(),
            "final_report_count": final_report_count,
            "import_batch_count": db.query(ImportBatch).count(),
            "measurement_sources": _measurement_sources(db),
        },
        "data_quality": _data_quality(db),
        "model": {
            "active_mode": model_status["active_mode"],
            "active_backend": model_status["active_backend"],
            "input_schema_version": model_status["input_schema_version"],
            "surrogate_model_version": model_status["surrogate_model_version"],
            "artifacts": model_status["artifacts"],
        },
        "exports": [
            {"name": "基础队列表", "endpoint": "/exports/cohort-table.csv", "available": True},
            {"name": "测量表", "endpoint": "/exports/measurements.csv", "available": True},
            {"name": "分析研究表", "endpoint": "/exports/research-table.csv", "available": True},
            {"name": "研究数据包 ZIP", "endpoint": "/exports/research-package.zip", "available": True},
        ],
        "latest": {
            "analysis": _latest_analysis(db),
            "report": _latest_report(db),
            "final_report": _latest_report(db, final_only=True),
            "import_batch": _latest_import_batch(db),
        },
        "readiness": [
            {"key": "dataset_spec", "label": "数据集规范", "available": True},
            {"key": "csv_validation", "label": "CSV 导入前校验", "available": True},
            {"key": "csv_preview", "label": "导入预览与质控评分", "available": True},
            {"key": "csv_commit", "label": "CSV 真实导入入库", "available": True},
            {"key": "import_batch_rollback", "label": "导入批次审计与回滚", "available": True},
            {"key": "research_package", "label": "研究数据包导出", "available": True},
            {"key": "model_self_check", "label": "模型接入自检", "available": True},
            {"key": "multi_nodule_analysis", "label": "多结节独立分析", "available": True},
            {"key": "editable_report", "label": "医生编辑确认报告", "available": True},
            {"key": "risk_trace", "label": "风险评分版本追踪", "available": True},
        ],
        "actions": _actions(model_status, analysis_count, final_report_count, real_dicom_count),
    }
