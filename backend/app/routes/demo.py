from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models import AnalysisResult, Nodule, Patient, Report, ReportAuditLog, ReportVersion, Study
from ..pipeline.analysis import run_patient_analysis
from ..pipeline.training import JSON_ARTIFACT, TRAINING_REPORT, train_temporal_model, training_readiness
from ..seed import seed_demo_data
from .reports import _add_report_version, build_report_markdown

router = APIRouter(prefix="/demo", tags=["demo"])

REPRESENTATIVE_CODES = ["SYN-LN-2026-001", "SYN-LN-2026-004", "SYN-LN-2026-008", "SYN-LN-2026-011"]


def _synthetic_patients(db: Session) -> list[Patient]:
    return db.query(Patient).filter(Patient.patient_code.like("SYN-LN-2026-%")).all()


def _clear_demo_outputs(db: Session) -> dict[str, int]:
    patients = _synthetic_patients(db)
    patient_ids = [patient.id for patient in patients]
    if not patient_ids:
        return {"reports_deleted": 0, "analyses_deleted": 0, "artifacts_deleted": 0}
    analyses = db.query(AnalysisResult).filter(AnalysisResult.patient_id.in_(patient_ids)).all()
    analysis_ids = [analysis.id for analysis in analyses]
    reports = db.query(Report).filter(Report.patient_id.in_(patient_ids)).all()
    report_ids = [report.id for report in reports]
    reports_deleted = len(report_ids)
    analyses_deleted = len(analysis_ids)
    if report_ids:
        db.query(ReportVersion).filter(ReportVersion.report_id.in_(report_ids)).delete(synchronize_session=False)
        db.query(ReportAuditLog).filter(ReportAuditLog.report_id.in_(report_ids)).delete(synchronize_session=False)
        db.query(Report).filter(Report.id.in_(report_ids)).delete(synchronize_session=False)
    if analysis_ids:
        db.query(AnalysisResult).filter(AnalysisResult.id.in_(analysis_ids)).delete(synchronize_session=False)
    artifacts_deleted = 0
    for artifact in [JSON_ARTIFACT, TRAINING_REPORT]:
        path = Path(artifact)
        if path.exists():
            path.unlink()
            artifacts_deleted += 1
    db.commit()
    return {"reports_deleted": reports_deleted, "analyses_deleted": analyses_deleted, "artifacts_deleted": artifacts_deleted}


def _load_patient(db: Session, code: str) -> Patient | None:
    return (
        db.query(Patient)
        .options(
            joinedload(Patient.studies).joinedload(Study.measurements),
            joinedload(Patient.studies).joinedload(Study.slices),
            joinedload(Patient.nodules).joinedload(Nodule.measurements),
        )
        .filter(Patient.patient_code == code)
        .first()
    )


def _create_analysis_and_report(db: Session, patient: Patient, nodule: Nodule) -> tuple[AnalysisResult, Report]:
    result = run_patient_analysis(patient, nodule.id)
    analysis = AnalysisResult(patient_id=patient.id, **result)
    db.add(analysis)
    db.flush()
    report = Report(
        patient_id=patient.id,
        analysis_id=analysis.id,
        title="肺结节多期 CT 智能随访报告",
        content_markdown=build_report_markdown(patient, analysis),
        doctor_opinion="演示默认意见：已核对 synthetic demo cohort 的目标结节跨期匹配和 AI 解释，建议按风险分层进行门诊随访或 MDT 讨论。",
        followup_plan=analysis.recommendation,
        status="draft",
    )
    db.add(report)
    db.flush()
    _add_report_version(report, db, "demo_created", "演示流程预生成草稿报告", "Demo")
    return analysis, report


@router.get("/walkthrough")
def demo_walkthrough(db: Session = Depends(get_db)) -> dict[str, Any]:
    readiness = training_readiness(db)
    return {
        "title": "肺结节随访系统 8 分钟演示脚本",
        "summary": "无真实数据时，使用 synthetic demo cohort 演示数据质量、模型训练、目标结节分析、报告确认和导出闭环。",
        "readiness": readiness,
        "steps": [
            {"order": 1, "page": "演示流程", "action": "点击“一键重置演示状态”", "expected": "清理旧 synthetic 分析/报告/训练 artifact，并重新写入 12 例示例队列。"},
            {"order": 2, "page": "演示流程", "action": "点击“预生成分析和报告”", "expected": "对高风险、稳定、缩小、多发结节代表病例生成分析和草稿报告。"},
            {"order": 3, "page": "系统总览", "action": "查看数据质量看板", "expected": "展示标签分布、缺失字段、随访间隔和可训练样本数。"},
            {"order": 4, "page": "模型状态", "action": "运行队列训练和模型自检", "expected": "生成 temporal_model.json/training_report.json，并完成 dry-run。"},
            {"order": 5, "page": "病例工作台", "action": "打开 SYN-LN-2026-004 或 SYN-LN-2026-008", "expected": "展示不同风险层级和目标结节随访曲线。"},
            {"order": 6, "page": "结构化报告", "action": "填入医生确认模板并导出 Word/打印 PDF", "expected": "完成医生确认、版本审计和报告导出展示。"},
        ],
    }


@router.post("/reset")
def reset_demo(db: Session = Depends(get_db)) -> dict[str, Any]:
    cleared = _clear_demo_outputs(db)
    seeded = seed_demo_data(db)
    return {"reset": True, "message": "Synthetic demo state reset without touching non-synthetic imported patients.", "cleared": cleared, "seeded": seeded}


@router.post("/prepare")
def prepare_demo(db: Session = Depends(get_db)) -> dict[str, Any]:
    seed_result = seed_demo_data(db)
    training_report = train_temporal_model(db, "Demo")
    created: list[dict[str, Any]] = []
    for code in REPRESENTATIVE_CODES:
        patient = _load_patient(db, code)
        if not patient or not patient.nodules:
            continue
        nodule = sorted(patient.nodules, key=lambda item: item.id)[0]
        analysis, report = _create_analysis_and_report(db, patient, nodule)
        created.append({"patient_id": patient.id, "patient_code": patient.patient_code, "nodule_id": nodule.id, "analysis_id": analysis.id, "report_id": report.id, "risk_level": analysis.risk_level, "risk_score": analysis.risk_score})
    db.commit()
    return {"prepared": True, "seeded": seed_result, "training": training_report, "created": created}
