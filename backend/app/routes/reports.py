import json
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models import AnalysisResult, Nodule, Patient, Report, Study
from ..schemas import ReportRead, ReportUpdate

router = APIRouter(prefix="/reports", tags=["reports"])


def _format_optional(value: float | None, digits: int = 0) -> str:
    return f"{value:.{digits}f}" if value is not None else "-"


def _model_explanation_markdown(analysis: AnalysisResult) -> str:
    try:
        risk = json.loads(analysis.features_json).get("risk", {})
    except json.JSONDecodeError:
        risk = {}
    contributions = risk.get("contributions", [])[:5]
    rows = [
        f"| {item.get('label', '-')} | {item.get('value', '-')} | {float(item.get('points', 0)):.3f} |"
        for item in contributions
    ]
    if not rows:
        rows = ["| - | - | - |"]
    return f"""## 模型解释

- 模型名称：{risk.get('model_name', '未记录')}
- 模型状态：{risk.get('model_status', '未记录')}
- 模型版本：{risk.get('model_version', '未记录')}
- 推理后端：{risk.get('backend', '未记录')}
- 输入时间点：{risk.get('model_input', {}).get('timepoint_count', '未记录')}

| 贡献因子 | 当前值 | 风险贡献 |
|---|---:|---:|
{chr(10).join(rows)}
"""


def _target_nodule(patient: Patient, analysis: AnalysisResult) -> Nodule | None:
    if analysis.nodule_id is not None:
        for nodule in patient.nodules:
            if nodule.id == analysis.nodule_id:
                return nodule
    try:
        payload = json.loads(analysis.features_json)
    except json.JSONDecodeError:
        payload = {}
    nodule_payload = payload.get("nodule") if isinstance(payload.get("nodule"), dict) else {}
    nodule_id = nodule_payload.get("id")
    if nodule_id is not None:
        for nodule in patient.nodules:
            if nodule.id == nodule_id:
                return nodule
    return patient.nodules[0] if patient.nodules else None


def build_report_markdown(patient: Patient, analysis: AnalysisResult) -> str:
    nodule = _target_nodule(patient, analysis)
    studies = sorted(patient.studies, key=lambda item: item.study_date)
    study_rows = []
    if nodule:
        measurement_by_study = {measurement.study_id: measurement for measurement in nodule.measurements}
        for study in studies:
            measurement = measurement_by_study.get(study.id)
            if measurement:
                study_rows.append(
                    f"| {study.study_date} | {measurement.diameter_mm:.1f} | {measurement.volume_mm3:.1f} | "
                    f"{measurement.mean_hu:.0f} | {_format_optional(measurement.min_hu)} | "
                    f"{_format_optional(measurement.max_hu)} | {_format_optional(measurement.roi_area_mm2, 1)} | "
                    f"{measurement.solid_component_percent:.0f}% |"
                )

    return f"""# 肺结节多期 CT 智能随访报告

## 患者信息

- 病例编号：{patient.patient_code}
- 姓名：{patient.name}
- 性别/年龄：{patient.sex} / {patient.age} 岁
- 吸烟史：{patient.smoking_history}
- 临床诊断：{patient.primary_diagnosis}

## 目标结节

- 结节位置：{nodule.lobe if nodule else '未记录'}
- 结节类型：{nodule.nodule_type if nodule else '未记录'}
- 基线描述：{nodule.baseline_impression if nodule else '未记录'}

## 多期 CT 定量对比

| 检查日期 | 最大径 mm | 体积 mm³ | 平均 CT 值 HU | 最小 HU | 最大 HU | ROI 面积 mm² | 实性成分 |
|---|---:|---:|---:|---:|---:|---:|---:|
{chr(10).join(study_rows)}

## 时序分析结果

- 配准质量评分：{analysis.registration_quality:.2f}
- 最大径变化：{analysis.diameter_change_mm:.1f} mm
- 体积变化：{analysis.volume_change_percent:.1f}%
- 密度变化：{analysis.density_change_hu:.1f} HU
- 体积倍增时间：{analysis.volume_doubling_time_days if analysis.volume_doubling_time_days else '未达到倍增'} 天
- AI 风险评分：{analysis.risk_score:.2f}
- AI 风险分层：{analysis.risk_level}

{_model_explanation_markdown(analysis)}
## 个体化随访建议

{analysis.recommendation}

本报告由本地演示版系统自动生成，仅作为临床辅助决策参考，最终诊疗意见需由医生结合完整病史、影像和指南确认。
"""


@router.post("/{analysis_id}", response_model=ReportRead)
def create_report(analysis_id: int, db: Session = Depends(get_db)) -> Report:
    analysis = db.get(AnalysisResult, analysis_id)
    if not analysis:
        raise HTTPException(status_code=404, detail="Analysis not found")

    patient = (
        db.query(Patient)
        .options(
            joinedload(Patient.studies).joinedload(Study.measurements),
            joinedload(Patient.nodules).joinedload(Nodule.measurements),
        )
        .filter(Patient.id == analysis.patient_id)
        .first()
    )
    if not patient:
        raise HTTPException(status_code=404, detail="Patient not found")

    report = Report(
        patient_id=patient.id,
        analysis_id=analysis.id,
        title="肺结节多期 CT 智能随访报告",
        content_markdown=build_report_markdown(patient, analysis),
        doctor_opinion="",
        followup_plan=analysis.recommendation,
        status="draft",
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


@router.put("/{report_id}", response_model=ReportRead)
def update_report(report_id: int, payload: ReportUpdate, db: Session = Depends(get_db)) -> Report:
    report = db.get(Report, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    if payload.status not in {"draft", "final"}:
        raise HTTPException(status_code=400, detail="status must be draft or final")
    report.content_markdown = payload.content_markdown
    report.doctor_opinion = payload.doctor_opinion
    report.followup_plan = payload.followup_plan
    report.status = payload.status
    report.finalized_at = datetime.utcnow() if payload.status == "final" else None
    db.commit()
    db.refresh(report)
    return report


@router.get("/{report_id}", response_model=ReportRead)
def get_report(report_id: int, db: Session = Depends(get_db)) -> Report:
    report = db.get(Report, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return report


@router.get("/patient/{patient_id}/latest", response_model=ReportRead | None)
def latest_report(patient_id: int, db: Session = Depends(get_db)) -> Report | None:
    return (
        db.query(Report)
        .filter(Report.patient_id == patient_id)
        .order_by(Report.created_at.desc())
        .first()
    )
