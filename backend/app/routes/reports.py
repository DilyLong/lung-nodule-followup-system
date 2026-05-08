import json
from datetime import datetime
from html import escape

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import HTMLResponse, Response
from sqlalchemy.orm import Session, joinedload

from ..database import get_db
from ..models import AnalysisResult, Nodule, Patient, Report, ReportAuditLog, ReportVersion, Study
from ..schemas import ReportAuditRead, ReportRead, ReportUpdate, ReportVersionRead

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


def _followup_interval_summary(studies: list[Study]) -> str:
    ordered = sorted(studies, key=lambda item: item.study_date)
    if len(ordered) < 2:
        return "随访时间点不足，建议补充既往或后续薄层 CT。"
    intervals = [(ordered[index].study_date - ordered[index - 1].study_date).days for index in range(1, len(ordered))]
    return "；".join(f"T{index}→T{index + 1}: {days} 天" for index, days in enumerate(intervals, start=1))


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


def _structured_recommendation(analysis: AnalysisResult) -> dict[str, str]:
    try:
        payload = json.loads(analysis.features_json)
    except json.JSONDecodeError:
        payload = {}
    recommendation = payload.get("recommendation")
    return recommendation if isinstance(recommendation, dict) else {}


def _risk_followup_window(level: str) -> str:
    if level == "高风险":
        return "1–3 个月内复查或 MDT 评估"
    if level == "中风险":
        return "3–6 个月复查薄层 CT"
    return "6–12 个月复查薄层 CT，稳定后延长间隔"


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

    structured = _structured_recommendation(analysis)
    report_number = f"LNF-{patient.patient_code}-{analysis.id:04d}"
    return f"""# 肺结节多期 CT 智能随访报告

## 报告抬头

- 医疗机构：华中科技大学同济医学院附属协和医院（演示模板）
- 科室：胸外科 / 影像科联合随访门诊
- 报告编号：{report_number}
- 报告版本：草稿 v1

## 患者信息

- 病例编号：{patient.patient_code}
- 姓名：{patient.name}
- 性别/年龄：{patient.sex} / {patient.age} 岁
- 吸烟史：{patient.smoking_history}
- 临床诊断：{patient.primary_diagnosis}

## 目标结节

- 结节位置：{nodule.lobe if nodule else '未记录'}
- 结节类型：{nodule.nodule_type if nodule else '未记录'}
- 临床标签：{nodule.clinical_label if nodule else '未记录'}
- 病理标签：{nodule.pathology_label if nodule else '未记录'}
- 基线描述：{nodule.baseline_impression if nodule else '未记录'}
- 随访间隔：{_followup_interval_summary(studies)}

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
## 医生确认清单

| 确认项目 | 状态/说明 |
|---|---|
| 原始 DICOM 与历史报告已核对 | 待医生确认 |
| 目标结节跨期匹配一致性 | 待医生确认 |
| ROI/测量误差是否可接受 | 待医生确认 |
| 指南建议是否适合患者整体情况 | 待医生确认 |
| 建议随访窗口 | {_risk_followup_window(analysis.risk_level)} |

## AI 风险评分、指南参考与医生确认

| 类别 | 内容 |
|---|---|
| AI 风险评分 | {structured.get('ai_risk_summary', analysis.recommendation)} |
| 风险依据 | {structured.get('clinical_rationale', '未记录')} |
| 指南/规则参考 | {structured.get('guideline_reference', '未记录')} |
| 规则建议 | {structured.get('rule_based_plan', structured.get('followup_plan', analysis.recommendation))} |
| 医生最终意见 | 待医生在确认区填写 |

{structured.get('doctor_confirmation_required', 'AI 输出仅作为辅助决策参考，最终诊疗意见需由医生确认。')}

本报告由本地演示版系统自动生成，仅作为临床辅助决策参考，最终诊疗意见需由医生结合完整病史、影像和指南确认。
"""


def _final_markdown(report: Report) -> str:
    return f"""{report.content_markdown.strip()}

## 医生编辑确认

- 医生意见：{report.doctor_opinion or '未填写'}
- 确认随访建议：{report.followup_plan or '未填写'}
- 医生签名：________________
- 确认时间：{report.finalized_at or '未确认'}
"""


def _markdown_to_html(markdown: str) -> str:
    lines = markdown.splitlines()
    chunks: list[str] = []
    index = 0
    while index < len(lines):
        line = lines[index].strip()
        if not line:
            index += 1
            continue
        if line.startswith("# "):
            chunks.append(f"<h1>{escape(line[2:])}</h1>")
            index += 1
            continue
        if line.startswith("## "):
            chunks.append(f"<h2>{escape(line[3:])}</h2>")
            index += 1
            continue
        if line.startswith("|"):
            table_lines = []
            while index < len(lines) and lines[index].strip().startswith("|"):
                table_lines.append(lines[index].strip())
                index += 1
            rows = []
            for table_line in table_lines:
                cells = [cell.strip() for cell in table_line.strip("|").split("|")]
                if all(set(cell) <= {"-", ":"} and len(cell) >= 3 for cell in cells):
                    continue
                rows.append(cells)
            if rows:
                header, *body = rows
                head = "".join(f"<th>{escape(cell)}</th>" for cell in header)
                body_html = "".join("<tr>" + "".join(f"<td>{escape(cell)}</td>" for cell in row) + "</tr>" for row in body)
                chunks.append(f"<table><thead><tr>{head}</tr></thead><tbody>{body_html}</tbody></table>")
            continue
        if line.startswith("- "):
            items = []
            while index < len(lines) and lines[index].strip().startswith("- "):
                items.append(lines[index].strip()[2:])
                index += 1
            chunks.append("<ul>" + "".join(f"<li>{escape(item)}</li>" for item in items) + "</ul>")
            continue
        paragraph = []
        while index < len(lines):
            next_line = lines[index].strip()
            if not next_line or next_line.startswith(("# ", "## ", "|", "- ")):
                break
            paragraph.append(next_line)
            index += 1
        chunks.append(f"<p>{escape(' '.join(paragraph))}</p>")
    return "\n".join(chunks)


def _report_html(report: Report) -> str:
    return f"""<!doctype html>
<html>
<head>
  <meta charset=\"utf-8\" />
  <title>{escape(report.title)}</title>
  <style>
    body {{ font-family: SimSun, \"Microsoft YaHei\", Arial, sans-serif; line-height: 1.75; color: #111827; max-width: 920px; margin: 32px auto; }}
    h1 {{ text-align: center; font-size: 24pt; }}
    h2 {{ font-size: 15pt; border-bottom: 1px solid #d1d5db; padding-bottom: 6pt; margin-top: 22pt; }}
    table {{ width: 100%; border-collapse: collapse; margin: 12pt 0; }}
    th, td {{ border: 1px solid #9ca3af; padding: 6pt 8pt; text-align: left; }}
    th {{ background: #f3f4f6; }}
    .meta {{ color: #64748b; text-align: center; margin-bottom: 18pt; }}
    @media print {{ body {{ margin: 12mm auto; }} .no-print {{ display: none; }} }}
  </style>
</head>
<body>
  <div class=\"meta\">报告状态：{escape(report.status)} · 报告编号：{report.id}</div>
  {_markdown_to_html(_final_markdown(report))}
</body>
</html>"""


def _next_version_number(report_id: int, db: Session) -> int:
    latest = db.query(ReportVersion).filter(ReportVersion.report_id == report_id).order_by(ReportVersion.version_number.desc()).first()
    return (latest.version_number if latest else 0) + 1


def _add_report_version(report: Report, db: Session, event: str, message: str, operator: str = "系统") -> None:
    db.add(
        ReportVersion(
            report_id=report.id,
            version_number=_next_version_number(report.id, db),
            status=report.status,
            content_markdown=report.content_markdown,
            doctor_opinion=report.doctor_opinion,
            followup_plan=report.followup_plan,
            operator=operator,
        )
    )
    db.add(ReportAuditLog(report_id=report.id, event=event, message=message, operator=operator))


@router.post("/{analysis_id}", response_model=ReportRead)
def create_report(analysis_id: int, operator: str = "系统", db: Session = Depends(get_db)) -> Report:
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
    db.flush()
    _add_report_version(report, db, "created", "创建报告草稿 v1", operator)
    db.commit()
    db.refresh(report)
    return report


@router.put("/{report_id}", response_model=ReportRead)
def update_report(report_id: int, payload: ReportUpdate, operator: str = "系统", db: Session = Depends(get_db)) -> Report:
    report = db.get(Report, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    if payload.status not in {"draft", "final"}:
        raise HTTPException(status_code=400, detail="status must be draft or final")
    if report.status == "final":
        unchanged = (
            payload.status == "final"
            and payload.content_markdown == report.content_markdown
            and payload.doctor_opinion == report.doctor_opinion
            and payload.followup_plan == report.followup_plan
        )
        if not unchanged:
            raise HTTPException(status_code=409, detail="Final report is locked; create a new report to revise clinical content")
    report.content_markdown = payload.content_markdown
    report.doctor_opinion = payload.doctor_opinion
    report.followup_plan = payload.followup_plan
    report.status = payload.status
    report.finalized_at = datetime.utcnow() if payload.status == "final" else None
    _add_report_version(report, db, "finalized" if payload.status == "final" else "draft_saved", "确认最终版报告" if payload.status == "final" else "保存报告草稿", operator)
    db.commit()
    db.refresh(report)
    return report


@router.get("/{report_id}/export.doc")
def export_report_doc(report_id: int, db: Session = Depends(get_db)) -> Response:
    report = db.get(Report, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    filename = f"report-{report.patient_id}-{report.id}.doc"
    return Response(
        content=_report_html(report),
        media_type="application/msword; charset=utf-8",
        headers={"Content-Disposition": f'attachment; filename="{filename}"'},
    )


@router.get("/{report_id}/print.html")
def export_report_print_html(report_id: int, db: Session = Depends(get_db)) -> HTMLResponse:
    report = db.get(Report, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    return HTMLResponse(_report_html(report))


@router.post("/{report_id}/revisions", response_model=ReportRead)
def create_report_revision(report_id: int, operator: str = "系统", db: Session = Depends(get_db)) -> Report:
    report = db.get(Report, report_id)
    if not report:
        raise HTTPException(status_code=404, detail="Report not found")
    revision = Report(
        patient_id=report.patient_id,
        analysis_id=report.analysis_id,
        title=report.title,
        content_markdown=report.content_markdown,
        doctor_opinion=report.doctor_opinion,
        followup_plan=report.followup_plan,
        status="draft",
    )
    db.add(revision)
    db.flush()
    _add_report_version(revision, db, "revision_created", f"基于报告 {report.id} 创建修订草稿", operator)
    db.commit()
    db.refresh(revision)
    return revision


@router.get("/{report_id}/versions", response_model=list[ReportVersionRead])
def list_report_versions(report_id: int, db: Session = Depends(get_db)) -> list[ReportVersion]:
    return db.query(ReportVersion).filter(ReportVersion.report_id == report_id).order_by(ReportVersion.version_number).all()


@router.get("/{report_id}/audit", response_model=list[ReportAuditRead])
def list_report_audit(report_id: int, db: Session = Depends(get_db)) -> list[ReportAuditLog]:
    return db.query(ReportAuditLog).filter(ReportAuditLog.report_id == report_id).order_by(ReportAuditLog.created_at).all()


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
