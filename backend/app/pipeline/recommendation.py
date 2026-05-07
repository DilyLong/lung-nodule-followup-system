from typing import Any


def recommend_followup(risk: dict[str, Any], features: dict[str, Any], nodule_type: str) -> str:
    level = risk["risk_level"]
    vdt = features.get("volume_doubling_time_days")
    solid_delta = features.get("solid_component_change_percent", 0)

    if level == "高风险":
        return "AI 评估提示高风险进展倾向。建议 1-3 个月内胸外科/影像科 MDT 复核，结合薄层 CT、增强检查或病理获取可能性评估进一步诊疗。"
    if level == "中风险":
        detail = ""
        if vdt and vdt < 900:
            detail += f"体积倍增时间约 {vdt} 天，"
        if solid_delta > 5:
            detail += f"实性成分增加约 {solid_delta}%，"
        return f"AI 评估提示中等风险。{detail}建议 3-6 个月复查薄层胸部 CT，并由同一算法流程进行动态对比。"
    if "纯磨玻璃" in nodule_type:
        return "AI 评估提示低风险且动态稳定。建议 12 个月复查薄层胸部 CT，若持续稳定可延长随访间隔。"
    return "AI 评估提示低风险。建议 6-12 个月复查薄层胸部 CT，并结合患者危险因素由医生确认随访间隔。"
