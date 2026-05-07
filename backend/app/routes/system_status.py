from __future__ import annotations

from datetime import datetime, timezone
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models import AnalysisResult, Nodule, NoduleMeasurement, Patient, Report, Study
from ..pipeline.model import model_runtime_status

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


@router.get("/status")
def get_system_status(db: Session = Depends(get_db)) -> dict[str, Any]:
    model_status = model_runtime_status()
    final_report_count = db.query(Report).filter(Report.status == "final").count()
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
            "analysis_count": db.query(AnalysisResult).count(),
            "report_count": db.query(Report).count(),
            "final_report_count": final_report_count,
        },
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
        },
        "readiness": [
            {"key": "dataset_spec", "label": "数据集规范", "available": True},
            {"key": "csv_validation", "label": "CSV 导入前校验", "available": True},
            {"key": "research_package", "label": "研究数据包导出", "available": True},
            {"key": "model_self_check", "label": "模型接入自检", "available": True},
            {"key": "multi_nodule_analysis", "label": "多结节独立分析", "available": True},
            {"key": "editable_report", "label": "医生编辑确认报告", "available": True},
            {"key": "risk_trace", "label": "风险评分版本追踪", "available": True},
        ],
    }
