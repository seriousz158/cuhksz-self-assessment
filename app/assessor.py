from __future__ import annotations

import json
import re
from datetime import datetime
from typing import Any

from openai import OpenAI

from app.config import Settings
from app.models import (
    ApplicantPath,
    ApplicantProfile,
    AssessResponse,
    AssessmentReport,
    FitLevel,
    SourceSnippet,
)


PATH_LABELS = {
    ApplicantPath.mainland_gaokao: "内地高考",
    ApplicantPath.comprehensive_eval: "综合评价",
    ApplicantPath.hmt: "港澳台",
    ApplicantPath.international: "国际生",
}

# ── Province name mapping (short ↔ long, for fuzzy matching in source text) ──
PROVINCE_ALIASES: dict[str, list[str]] = {
    "天津": ["天津"],
    "北京": ["北京"],
    "上海": ["上海"],
    "重庆": ["重庆"],
    "广东": ["广东", "广东省"],
    "浙江": ["浙江", "浙江省"],
    "江苏": ["江苏", "江苏省"],
    "福建": ["福建", "福建省"],
    "山东": ["山东", "山东省"],
    "四川": ["四川", "四川省"],
    "安徽": ["安徽", "安徽省"],
    "江西": ["江西", "江西省"],
    "河北": ["河北", "河北省"],
    "河南": ["河南", "河南省"],
    "湖北": ["湖北", "湖北省"],
    "湖南": ["湖南", "湖南省"],
    "广西": ["广西"],
    "贵州": ["贵州", "贵州省"],
    "云南": ["云南", "云南省"],
    "辽宁": ["辽宁", "辽宁省"],
    "黑龙江": ["黑龙江", "黑龙江省"],
    "陕西": ["陕西", "陕西省"],
}


def validate_profile(profile: ApplicantProfile) -> list[str]:
    """Return human-readable labels for *critical* missing fields.

    Only fields that genuinely block a useful assessment are treated as
    hard-required.  Soft fields (english_level, budget, adaptability) are
    still useful to the LLM but won't prevent it from being called.
    """
    missing: list[str] = []
    hard_required = {
        "region": "地区/省份/国家",
        "exam_type": "考试类型",
        "score_summary": "成绩/排名/等级",
        "intended_major": "意向专业",
    }
    for field_name, label in hard_required.items():
        if not getattr(profile, field_name).strip():
            missing.append(label)
    return missing


def soft_missing_labels(profile: ApplicantProfile) -> list[str]:
    """Return labels for fields the student left blank but that are *not*
    blocking — the LLM can still produce a useful report without them."""
    soft: list[str] = []
    soft_fields = {
        "english_level": "英语能力",
        "budget": "预算情况",
        "adaptability": "适应能力",
    }
    for field_name, label in soft_fields.items():
        if not getattr(profile, field_name).strip():
            soft.append(label)
    return soft


def _match_province(text: str, region: str) -> bool:
    """Check whether *text* mentions the student's province (fuzzy)."""
    aliases = PROVINCE_ALIASES.get(region, [region])
    return any(alias in text for alias in aliases)


def extract_score_context(sources: list[dict[str, Any]], region: str) -> str:
    """Extract structured score-line context from retrieved source chunks.

    Returns a concise markdown summary that is injected into the LLM prompt so
    the model has a "cheat sheet" of the most relevant numbers before it reads
    the full source snippets.
    """
    combined = "\n".join(source.get("text", "") for source in sources)

    province_lines: list[str] = []
    national_stats: list[str] = []
    neighbour_lines: list[str] = []
    english_stats: list[str] = []

    # ── 1. Province-specific score lines ──
    province_pattern = re.compile(
        r"^\s*\|?\s*(" + re.escape(region) + r")\s*\|[^|]*\|?\s*([\d]+)\s*\|?\s*([\d]+|-)\s*\|?",
        re.MULTILINE,
    )
    for match in province_pattern.finditer(combined):
        score = match.group(2)
        rank = match.group(3)
        rank_str = f"，位次 {rank}" if rank and rank != "-" else "（位次未公布）"
        province_lines.append(f"- {match.group(1)}：最低录取分 **{score}**{rank_str}")

    # ── 2. National-level summary statistics ──
    for pattern, label in [
        (r"物理类.*?前\s*([\d]+)%", "物理类位次前{}%"),
        (r"历史类.*?前\s*([\d]+)%", "历史类位次前{}%"),
        (r"录取学生高考英语平均分高达\s*([\d]+)\s*分", "录取学生英语平均 {} 分"),
        (r"最低分区间[：:]\s*([\d]+)\s*[-–—]\s*([\d]+)", "全国最低分区间 {}–{}"),
        (r"全国共录取\s*([\d,]+)\s*名本科新生", "2025 年全国录取 {} 名本科新生"),
    ]:
        m = re.search(pattern, combined)
        if m:
            national_stats.append(f"- {label.format(*m.groups())}")

    # ── 3. English score stats ──
    eng_m = re.search(r"高考英语平均分[^\d]*([\d]+)", combined)
    if eng_m:
        english_stats.append(f"- 录取学生高考英语平均分：**{eng_m.group(1)}** 分")

    # ── 4. Neighbour / similar-tier province lines as cross-reference ──
    neighbour_provinces = ["北京", "河北", "河南", "山东", "辽宁", "陕西", "安徽"]
    for neighbour in neighbour_provinces:
        if neighbour == region:
            continue
        n_pat = re.compile(
            r"^\s*\|?\s*(" + re.escape(neighbour) + r")\s*\|[^|]*\|?\s*([\d]+)\s*\|?\s*([\d]+|-)\s*\|?",
            re.MULTILINE,
        )
        for nm in n_pat.finditer(combined):
            rk = nm.group(3)
            rk_str = f"，位次 {rk}" if rk and rk != "-" else ""
            neighbour_lines.append(f"- {nm.group(1)}：最低 {nm.group(2)} 分{rk_str}")
            break  # one line per neighbour is enough

    # ── Assemble ──
    parts: list[str] = []
    if province_lines:
        parts.append("**该省已知录取数据**：\n" + "\n".join(province_lines))
    else:
        # Build a richer fallback when no province-specific line is found
        fallback_lines = [
            f"**该省已知录取数据**：未在官方和第三方资料中找到 {region} 的明确分省分数线。",
            "",
            "⚠️ 重要：这不代表无法评估。请使用以下方法定位学生竞争力：",
        ]
        if national_stats:
            fallback_lines.append(
                "- **全国百分位参照**：港中深在全国物理类/选考最低录取分稳居各省市考生**前 2%**，"
                "历史类稳居**前 1%**。如果学生在所在省份的高考排名/分数处于前 2%（物理类）"
                "或前 1%（历史类），则具备高度竞争力。"
            )
            fallback_lines.append(
                "- **全国分数区间参照**：2025 年全国最低分区间约为 603–666 分。"
                "不同省份因高考难度和分数线差异，具体分数会有波动，"
                "但考生在本省的百分位排名是稳定的参照。"
            )
        if english_stats:
            fallback_lines.append(
                "- **英语能力参照**：录取学生高考英语平均分高达 **136** 分。"
                "即使缺乏省份分数线，英语成绩仍是重要参考维度。"
            )
        if neighbour_lines:
            fallback_lines.append(
                "- **毗邻省份数据**（可用于大致参照，注意省份间高考难度和分数线差异）："
            )
        parts.append("\n".join(fallback_lines))

    if national_stats:
        parts.append("**全国统计数据（可用于定位参考）**：\n" + "\n".join(national_stats))
    if english_stats:
        parts.append("**英语成绩参考**：\n" + "\n".join(english_stats))
    if neighbour_lines:
        parts.append("**毗邻/同类省份参考**：\n" + "\n".join(neighbour_lines))

    if not parts:
        return "（未从资料中提取到可量化的分数上下文，请完全依赖下方的原始资料片段。）"

    return "\n\n".join(parts)


def build_retrieval_query(profile: ApplicantProfile) -> str:
    path_label = PATH_LABELS[profile.applicant_path]
    parts = [
        path_label,
        profile.region,
        profile.exam_type,
        profile.score_summary,
        profile.english_level,
        profile.intended_major,
        profile.budget,
        profile.constraints,
        "招生要求 申请条件 专业 选科 选考 学费 奖学金 英文教学 录取建议 分数线 位次 体检",
    ]
    return " ".join(part for part in parts if part)


def insufficient_response(
    profile: ApplicantProfile,
    missing: list[str],
    sources: list[dict[str, Any]],
) -> AssessResponse:
    source_models = [SourceSnippet(**source) for source in sources]

    # Build a specific guidance block from the retrieved official sources
    source_tips: list[str] = []
    for src in source_models[:5]:
        source_tips.append(f"根据「{src.title}」，{src.category}信息对评估至关重要。")
    if not source_tips:
        source_tips.append("当前知识库中暂未找到与你的申请通道匹配的资料，请先运行「采集资料」并「重建索引」。")

    action_plan: list[str] = [f"补充：{field}" for field in missing]
    action_plan.append("补充完毕后重新提交，系统将调用云端模型生成详细分析报告。")

    report = AssessmentReport(
        fit_level=FitLevel.insufficient_data,
        conclusion=(
            f"缺少 {len(missing)} 项关键信息（{'、'.join(missing)}），"
            "暂时无法生成深度分析报告。请补充后再试。"
        ),
        key_evidence=source_tips,
        risks=[
            "成绩、考试类型和意向专业是判断匹配度的最低门槛信息，缺少任一项都无法给出有意义的评估。",
            "招生政策因省份和申请通道差异很大，没有具体地区会被放到错误的规则里评估。",
        ],
        action_plan=action_plan,
        sources=source_models,
    )
    return AssessResponse(status="insufficient_data", report=report, missing_fields=missing)


def call_llm_for_report(
    profile: ApplicantProfile,
    sources: list[dict[str, Any]],
    settings: Settings,
) -> AssessmentReport:
    if not settings.llm_configured:
        raise RuntimeError(
            "Cloud LLM is not configured. Set OPENAI_API_KEY and MODEL_NAME in .env. "
            "If you use a compatible provider, also set OPENAI_BASE_URL."
        )

    client = OpenAI(api_key=settings.openai_api_key, base_url=settings.openai_base_url)
    prompt = build_report_prompt(profile, sources)
    response = client.chat.completions.create(
        model=settings.model_name,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a helpful undergraduate admissions self-assessment assistant "
                    "for The Chinese University of Hong Kong, Shenzhen. "
                    "Base your analysis on the provided official source snippets. "
                    "When a snippet contains relevant information, use it directly and cite it by index. "
                    "When no snippet covers a particular question, note it briefly but still "
                    "give your best reading of what the available information implies for the student. "
                    "Never invent policy details or numbers. "
                    "Never give an admission probability or guarantee. "
                    "Return valid JSON only."
                ),
            },
            {"role": "user", "content": prompt},
        ],
        temperature=0.2,
    )
    content = response.choices[0].message.content or ""
    data = parse_json_object(content)
    normalized = normalize_report_data(data)
    normalized["sources"] = sources
    return AssessmentReport(**normalized)


def build_report_prompt(profile: ApplicantProfile, sources: list[dict[str, Any]]) -> str:
    source_text = "\n\n".join(
        f"[{index}] {source['title']}\nURL: {source['url']}\n片段: {source['text']}"
        for index, source in enumerate(sources, start=1)
    )
    score_context = extract_score_context(sources, profile.region)
    return f"""
请基于"官方资料片段"和"学生画像"输出 JSON。

硬性要求：
1. 只能使用官方资料片段，不要编造政策。
2. 不要输出"录取概率""百分比概率""保证录取"等表达。
3. 基于已有资料给学生最优判断。当某维度完全没有资料支撑时才说明缺什么；有部分资料时，基于已有信息给出定性分析，同时诚实标注信息缺口。
4. fit_level 只能是：高度匹配、有条件匹配、风险较高、暂不建议、信息不足。
5. key_evidence 必须说明依据来自哪些官方资料（引用编号 [N]）。
6. academic_match：综合学生成绩、所在省份特征和下方"分数上下文摘要"给出定性判断。省份分数线存在时直接对比；分数线缺失但有全国统计数据时，用全国统计数据做参照。排名极高+英语远超平均就是实质性的积极信号——即使缺乏精确的全省排名换算，也不应判定为"信息不足"。
7. major_match：如果资料中有该专业信息，分析匹配度；没有则说明"官方资料中暂未收录该专业的详细要求"，不要编造。
8. 每一项分析都要有内容，不要留空字段。
9. fit_level 判定指引：
   - "高度匹配"：学生成绩/排名明显高于该省已知录取线，或虽缺精确分数线但全国统计数据明确支持其竞争力
   - "有条件匹配"：成绩接近或可能超过已知分数线，或部分数据缺失但可推断方向积极
   - "风险较高"：成绩明显低于已知线，或有硬性条件不满足
   - "暂不建议"：多条硬性条件不满足
   - "信息不足"：**仅当**连最基本的定位参考（如所在省份分数线、可比省份数据、全国统计数据）都完全没有时才使用。只要有一条基准线可用于定位，就不应判定为信息不足。

分数上下文摘要：
{score_context}

学生画像：
{json.dumps(_model_dump(profile), ensure_ascii=False, indent=2)}

官方资料片段：
{source_text}

请返回这个 JSON 结构：
{{
  "fit_level": "高度匹配/有条件匹配/风险较高/暂不建议/信息不足",
  "conclusion": "一段总判断",
  "key_evidence": ["依据1", "依据2"],
  "academic_match": "学术成绩匹配分析",
  "major_match": "专业匹配分析",
  "language_and_adaptability": "语言和适应性分析",
  "cost_and_scholarship_risk": "费用和奖学金风险分析",
  "risks": ["风险1", "风险2"],
  "action_plan": ["下一步1", "下一步2"]
}}
""".strip()


def parse_json_object(content: str) -> dict[str, Any]:
    cleaned = content.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```(?:json)?", "", cleaned).strip()
        cleaned = re.sub(r"```$", "", cleaned).strip()
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{.*\}", cleaned, re.S)
        if not match:
            raise ValueError(f"LLM did not return JSON: {content[:500]}")
        return json.loads(match.group(0))


def normalize_report_data(data: dict[str, Any]) -> dict[str, Any]:
    fit_level = str(data.get("fit_level", "")).strip()
    allowed = {item.value for item in FitLevel}
    if fit_level not in allowed:
        fit_level = FitLevel.conditional_fit.value

    return {
        "fit_level": fit_level,
        "conclusion": str(data.get("conclusion", "")).strip() or "系统已生成建议，但结论内容为空。",
        "key_evidence": _list_of_strings(data.get("key_evidence")),
        "academic_match": str(data.get("academic_match", "")).strip(),
        "major_match": str(data.get("major_match", "")).strip(),
        "language_and_adaptability": str(data.get("language_and_adaptability", "")).strip(),
        "cost_and_scholarship_risk": str(data.get("cost_and_scholarship_risk", "")).strip(),
        "risks": _list_of_strings(data.get("risks")),
        "action_plan": _list_of_strings(data.get("action_plan")),
    }


def _list_of_strings(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]
    if isinstance(value, str) and value.strip():
        return [value.strip()]
    return []


def history_record(profile: ApplicantProfile, response: AssessResponse) -> dict[str, Any]:
    return {
        "created_at": datetime.now().isoformat(timespec="seconds"),
        "profile": _model_dump(profile),
        "response": _model_dump(response),
    }


def _model_dump(model: Any) -> dict[str, Any]:
    if hasattr(model, "model_dump"):
        return model.model_dump()
    return model.dict()
