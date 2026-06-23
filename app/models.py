from __future__ import annotations

from enum import Enum
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ApplicantPath(str, Enum):
    mainland_gaokao = "mainland_gaokao"
    comprehensive_eval = "comprehensive_eval"
    hmt = "hmt"
    international = "international"


class FitLevel(str, Enum):
    strong_fit = "高度匹配"
    conditional_fit = "有条件匹配"
    high_risk = "风险较高"
    not_recommended = "暂不建议"
    insufficient_data = "信息不足"


class ApplicantProfile(BaseModel):
    applicant_path: ApplicantPath = Field(..., description="招生通道")
    region: str = Field("", description="省份/地区/国家")
    exam_type: str = Field("", description="考试类型，如高考、IB、A-Level、DSE、SAT")
    score_summary: str = Field("", description="成绩、排名、等级、分数线差距等")
    english_level: str = Field("", description="英语能力，如雅思/托福/高考英语/DSE English")
    intended_major: str = Field("", description="意向专业或学院")
    competitions_projects: str = Field("", description="竞赛、科研、活动、项目经历")
    budget: str = Field("", description="家庭预算、学费住宿费承受能力")
    adaptability: str = Field("", description="英文教学、深圳生活、独立学习等适应能力")
    constraints: str = Field("", description="必须满足的限制或担忧")

    @field_validator("*", mode="before")
    @classmethod
    def strip_strings(cls, value: Any) -> Any:
        if isinstance(value, str):
            return value.strip()
        return value


class AssessRequest(BaseModel):
    profile: ApplicantProfile
    save_history: bool = True


class SourceSnippet(BaseModel):
    title: str
    url: str
    category: str
    applicant_path: str
    score: float
    text: str


class AssessmentReport(BaseModel):
    fit_level: FitLevel
    conclusion: str
    key_evidence: list[str] = Field(default_factory=list)
    academic_match: str = ""
    major_match: str = ""
    language_and_adaptability: str = ""
    cost_and_scholarship_risk: str = ""
    risks: list[str] = Field(default_factory=list)
    action_plan: list[str] = Field(default_factory=list)
    sources: list[SourceSnippet] = Field(default_factory=list)
    privacy_note: str = "本次自评记录默认保存在本机 data/history，不会自动上传到第三方数据库。"
    disclaimer: str = "本结果不是港中深官方录取结论，也不是录取概率预测，只是基于官方资料和你填写的信息给出的建议。"


class AssessResponse(BaseModel):
    status: Literal["ok", "insufficient_data"]
    report: AssessmentReport
    missing_fields: list[str] = Field(default_factory=list)


class StatusResponse(BaseModel):
    model_config = ConfigDict(protected_namespaces=())

    documents: int
    chunks: int
    index_ready: bool
    llm_configured: bool
    embedding_model: str
    model_name: str


class ClearHistoryRequest(BaseModel):
    confirm_first: bool = False
    confirm_second: bool = False
    phrase: str = ""
