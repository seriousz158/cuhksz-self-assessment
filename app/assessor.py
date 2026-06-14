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


def validate_profile(profile: ApplicantProfile) -> list[str]:
    missing: list[str] = []
    required = {
        "region": "地区/省份/国家",
        "exam_type": "考试类型",
        "score_summary": "成绩/排名/等级",
        "english_level": "英语能力",
        "intended_major": "意向专业",
        "budget": "预算情况",
        "adaptability": "适应能力",
    }
    for field_name, label in required.items():
        if not getattr(profile, field_name).strip():
            missing.append(label)
    return missing


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
        "招生要求 申请条件 专业 学费 奖学金 英文教学 录取建议",
    ]
    return " ".join(part for part in parts if part)


def insufficient_response(profile: ApplicantProfile, missing: list[str], sources: list[dict[str, Any]]) -> AssessResponse:
    source_models = [SourceSnippet(**source) for source in sources]
    report = AssessmentReport(
        fit_level=FitLevel.insufficient_data,
        conclusion="信息不足，暂时不能判断你是否适合申请港中深本科。",
        key_evidence=[
            "你还没有提供足够的考试、英语、专业或预算信息。",
            "招生建议必须基于具体申请通道和成绩背景，不能凭空猜。",
        ],
        risks=["如果缺少成绩或申请通道，系统可能把你放到错误的招生规则里。"],
        action_plan=[f"补充：{field}" for field in missing],
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
                    "You are a cautious undergraduate admissions self-assessment assistant. "
                    "Use only the provided official source snippets. Do not invent policy. "
                    "Do not provide admission probability. Return valid JSON only."
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
    return f"""
请基于“官方资料片段”和“学生画像”输出 JSON。

硬性要求：
1. 只能使用官方资料片段，不要编造政策。
2. 不要输出“录取概率”“百分比概率”“保证录取”等表达。
3. 如果资料不足，要明确说还需要补充什么。
4. fit_level 只能是：高度匹配、有条件匹配、风险较高、暂不建议、信息不足。
5. key_evidence 必须说明依据来自哪些官方资料。

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
