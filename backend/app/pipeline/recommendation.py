from typing import Any


def structured_followup_recommendation(risk: dict[str, Any], features: dict[str, Any], nodule_type: str) -> dict[str, str]:
    level = risk["risk_level"]
    vdt = features.get("volume_doubling_time_days")
    solid_delta = features.get("solid_component_change_percent", 0)
    diameter_change = features.get("diameter_change_mm", 0)

    if level == "高风险":
        plan = "建议 1-3 个月内胸外科/影像科 MDT 复核，结合薄层 CT、增强检查或病理获取可能性评估进一步诊疗。"
        guideline = "参考 Fleischner/Lung-RADS 思路：出现明确增长、实性成分增加或形态恶性征时，应缩短随访并考虑多学科评估。"
    elif level == "中风险":
        plan = "建议 3-6 个月复查薄层胸部 CT，并由同一算法流程进行动态对比。"
        guideline = "参考指南原则：中等风险结节需短间隔复查确认增长趋势，避免单次测量误差导致过度处理。"
    elif "纯磨玻璃" in nodule_type:
        plan = "建议 12 个月复查薄层胸部 CT，若持续稳定可延长随访间隔。"
        guideline = "参考指南原则：稳定纯磨玻璃结节通常以长期影像随访为主。"
    else:
        plan = "建议 6-12 个月复查薄层胸部 CT，并结合患者危险因素由医生确认随访间隔。"
        guideline = "参考指南原则：低风险且稳定结节可适当延长复查间隔。"

    rationale_parts = [f"AI 风险分层为{level}"]
    if diameter_change:
        rationale_parts.append(f"最大径变化 {diameter_change} mm")
    if vdt:
        rationale_parts.append(f"体积倍增时间约 {vdt} 天")
    if solid_delta:
        rationale_parts.append(f"实性成分变化 {solid_delta}%")
    return {
        "ai_risk_summary": f"AI 评估提示{level}进展倾向。",
        "guideline_reference": guideline,
        "clinical_rationale": "；".join(rationale_parts) + "。",
        "followup_plan": plan,
    }


def recommend_followup(risk: dict[str, Any], features: dict[str, Any], nodule_type: str) -> str:
    recommendation = structured_followup_recommendation(risk, features, nodule_type)
    return f"{recommendation['ai_risk_summary']} {recommendation['clinical_rationale']} {recommendation['followup_plan']}"
