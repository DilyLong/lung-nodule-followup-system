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

REPRESENTATIVE_CASES: dict[str, dict[str, str]] = {
    "SYN-LN-2026-004": {
        "label": "高风险进展病例",
        "headline": "吸烟高危背景下右上肺实性结节快速增大，适合展示高风险评分、短间隔复查和 MDT 建议。",
        "demo_reason": "三期最大径由 7.0 mm 增至 11.7 mm，密度和毛刺/胸膜牵拉同步增加，能直观看到时序模型如何识别进展。",
    },
    "SYN-LN-2026-011": {
        "label": "稳定纯磨玻璃病例",
        "headline": "多发纯磨玻璃结节三期稳定，适合展示低风险随访和避免过度干预。",
        "demo_reason": "双肺纯磨玻璃结节直径、密度和实性成分长期稳定，可用于讲解多结节管理中的保守随访策略。",
    },
    "SYN-LN-2026-008": {
        "label": "炎性缩小病例",
        "headline": "实性炎性结节随访中逐渐缩小，适合展示动态变化如何降低风险分层。",
        "demo_reason": "最大径由 9.0 mm 降至 5.6 mm，密度同步下降，可展示系统区分恶性进展和炎性吸收的演示逻辑。",
    },
    "SYN-LN-2026-009": {
        "label": "多发结节差异化随访病例",
        "headline": "同一患者存在进展性部分实性结节和稳定对侧纯磨玻璃结节，适合展示目标结节独立分析。",
        "demo_reason": "左右肺结节风险不同，可用于说明为什么随访系统需要按目标结节分别建模、分别生成报告。",
    },
}

REPRESENTATIVE_CODES = list(REPRESENTATIVE_CASES)


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


def _latest_report_for_patient(db: Session, patient_id: int) -> Report | None:
    return db.query(Report).filter(Report.patient_id == patient_id).order_by(Report.created_at.desc()).first()


def _latest_analysis_for_patient(db: Session, patient_id: int) -> AnalysisResult | None:
    return db.query(AnalysisResult).filter(AnalysisResult.patient_id == patient_id).order_by(AnalysisResult.created_at.desc()).first()


def _representative_story(db: Session, code: str) -> dict[str, Any]:
    story = REPRESENTATIVE_CASES[code]
    patient = _load_patient(db, code)
    latest_report = _latest_report_for_patient(db, patient.id) if patient else None
    latest_analysis = _latest_analysis_for_patient(db, patient.id) if patient else None
    return {
        "patient_id": patient.id if patient else None,
        "patient_code": code,
        "name": patient.name if patient else "未加载",
        "label": story["label"],
        "headline": story["headline"],
        "demo_reason": story["demo_reason"],
        "nodule_count": len(patient.nodules) if patient else 0,
        "latest_report_id": latest_report.id if latest_report else None,
        "latest_report_status": latest_report.status if latest_report else None,
        "latest_analysis_id": latest_analysis.id if latest_analysis else None,
        "latest_risk_level": latest_analysis.risk_level if latest_analysis else None,
        "latest_risk_score": latest_analysis.risk_score if latest_analysis else None,
    }


def _demo_status(db: Session, readiness: dict[str, Any]) -> dict[str, Any]:
    patients = _synthetic_patients(db)
    patient_ids = [patient.id for patient in patients]
    analysis_count = db.query(AnalysisResult).filter(AnalysisResult.patient_id.in_(patient_ids)).count() if patient_ids else 0
    report_count = db.query(Report).filter(Report.patient_id.in_(patient_ids)).count() if patient_ids else 0
    latest_report = db.query(Report).filter(Report.patient_id.in_(patient_ids)).order_by(Report.created_at.desc()).first() if patient_ids else None
    latest_analysis = db.query(AnalysisResult).filter(AnalysisResult.patient_id.in_(patient_ids)).order_by(AnalysisResult.created_at.desc()).first() if patient_ids else None
    representative_stories = [_representative_story(db, code) for code in REPRESENTATIVE_CODES]
    return {
        "synthetic_patient_count": len(patients),
        "analysis_count": analysis_count,
        "report_count": report_count,
        "trained": readiness.get("artifact_exists", False),
        "training_report_exists": readiness.get("training_report_exists", False),
        "latest_report_id": latest_report.id if latest_report else None,
        "latest_report_status": latest_report.status if latest_report else None,
        "latest_analysis_id": latest_analysis.id if latest_analysis else None,
        "latest_analysis_risk_level": latest_analysis.risk_level if latest_analysis else None,
        "representative_ready_count": sum(1 for item in representative_stories if item["latest_report_id"]),
        "representative_total_count": len(representative_stories),
        "representative_stories": representative_stories,
    }


@router.get("/walkthrough")
def demo_walkthrough(db: Session = Depends(get_db)) -> dict[str, Any]:
    readiness = training_readiness(db)
    return {
        "title": "肺结节随访系统 8 分钟演示脚本",
        "summary": "无真实数据时，使用 synthetic demo cohort 演示数据质量、模型训练、目标结节分析、报告确认和导出闭环。",
        "readiness": readiness,
        "status": _demo_status(db, readiness),
        "safety_notice": {
            "title": "研究演示安全边界",
            "items": [
                "Synthetic demo cohort 不代表真实患者数据。",
                "AI 风险评分仅用于科研和产品演示，不可直接作为诊疗依据。",
                "上传真实 DICOM 前必须完成患者身份信息脱敏。",
                "最终随访和诊疗决策必须由医生结合完整病史、影像和指南确认。",
            ],
        },
        "steps": [
            {"order": 1, "page": "演示流程", "action": "点击“一键重置演示状态”", "expected": "清理旧 synthetic 分析/报告/训练 artifact，并重新写入 12 例示例队列。"},
            {"order": 2, "page": "演示流程", "action": "点击“预生成分析和报告”", "expected": "对高风险、稳定、缩小、多发结节代表病例生成分析和草稿报告。"},
            {"order": 3, "page": "系统总览", "action": "查看数据质量看板", "expected": "展示标签分布、缺失字段、随访间隔和可训练样本数。"},
            {"order": 4, "page": "模型状态", "action": "运行队列训练和模型自检", "expected": "生成 temporal_model.json/training_report.json，并完成 dry-run。"},
            {"order": 5, "page": "病例工作台", "action": "打开 SYN-LN-2026-004 或 SYN-LN-2026-009", "expected": "展示高风险进展和多发结节差异化随访两条代表故事线。"},
            {"order": 6, "page": "结构化报告", "action": "填入医生确认模板并导出 Word/打印 PDF", "expected": "完成医生确认、版本审计和报告导出展示。"},
        ],
    }


@router.get("/representative-cases")
def representative_cases(db: Session = Depends(get_db)) -> list[dict[str, Any]]:
    return [_representative_story(db, code) for code in REPRESENTATIVE_CODES]



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
        created.append({
            "patient_id": patient.id,
            "patient_code": patient.patient_code,
            "nodule_id": nodule.id,
            "analysis_id": analysis.id,
            "report_id": report.id,
            "risk_level": analysis.risk_level,
            "risk_score": analysis.risk_score,
            "story": REPRESENTATIVE_CASES[code],
        })
    db.commit()
    return {"prepared": True, "seeded": seed_result, "training": training_report, "created": created}
