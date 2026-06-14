from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class OfficialSource:
    source_id: str
    title: str
    url: str
    category: str
    applicant_path: str


OFFICIAL_SOURCES: list[OfficialSource] = [
    OfficialSource(
        "mainland_gaokao_2026",
        "香港中文大学（深圳）2026年夏季高考招生章程",
        "https://admissions.cuhk.edu.cn/article/2397",
        "招生章程",
        "mainland_gaokao",
    ),
    OfficialSource(
        "comprehensive_eval_overview",
        "综合评价招生",
        "https://admissions.cuhk.edu.cn/page/834",
        "综合评价",
        "comprehensive_eval",
    ),
    OfficialSource(
        "comprehensive_eval_zhejiang_2026",
        "香港中文大学（深圳）2026年浙江省“三位一体”综合评价招生简章",
        "https://admissions.cuhk.edu.cn/article/2391",
        "综合评价",
        "comprehensive_eval",
    ),
    OfficialSource(
        "comprehensive_eval_fujian_2026",
        "香港中文大学（深圳）2026年福建省综合评价招生简章",
        "https://admissions.cuhk.edu.cn/article/2381",
        "综合评价",
        "comprehensive_eval",
    ),
    OfficialSource(
        "comprehensive_eval_jiangsu_2026",
        "香港中文大学（深圳）2026年江苏省综合评价招生简章",
        "https://admissions.cuhk.edu.cn/article/2380",
        "综合评价",
        "comprehensive_eval",
    ),
    OfficialSource(
        "comprehensive_eval_shandong_2026",
        "香港中文大学（深圳）2026年山东省综合评价招生简章",
        "https://admissions.cuhk.edu.cn/article/2379",
        "综合评价",
        "comprehensive_eval",
    ),
    OfficialSource(
        "comprehensive_eval_shanghai_2026",
        "香港中文大学（深圳）2026年上海市综合评价招生简章",
        "https://admissions.cuhk.edu.cn/article/2378",
        "综合评价",
        "comprehensive_eval",
    ),
    OfficialSource(
        "comprehensive_eval_guangdong_2026",
        "香港中文大学（深圳）2026年广东省综合评价招生简章",
        "https://admissions.cuhk.edu.cn/article/2377",
        "综合评价",
        "comprehensive_eval",
    ),
    OfficialSource(
        "hmt_overview",
        "港澳台招生",
        "https://admissions.cuhk.edu.cn/taxonomy/term/166",
        "港澳台招生",
        "hmt",
    ),
    OfficialSource(
        "hmt_joint_exam_2026",
        "香港中文大学（深圳）2026年联合招收华侨港澳台学生招生简章",
        "https://admissions.cuhk.edu.cn/article/2242",
        "港澳台招生",
        "hmt",
    ),
    OfficialSource(
        "taiwan_gsat_2026",
        "香港中文大学（深圳）2026年依据台湾地区学测成绩招收台湾高中毕业生招生简章",
        "https://admissions.cuhk.edu.cn/article/2238",
        "港澳台招生",
        "hmt",
    ),
    OfficialSource(
        "hongkong_dse_2026",
        "香港中文大学（深圳）2026年招收香港中学文凭考试学生招生简章",
        "https://admissions.cuhk.edu.cn/article/2236",
        "港澳台招生",
        "hmt",
    ),
    OfficialSource(
        "macau_recommendation_2026",
        "香港中文大学（深圳）2026年澳门保送生招生简章",
        "https://admissions.cuhk.edu.cn/article/2234",
        "港澳台招生",
        "hmt",
    ),
    OfficialSource(
        "macau_joint_exam_2026",
        "香港中文大学（深圳）2026年依据澳门“四校联考”成绩招收澳门学生简章",
        "https://admissions.cuhk.edu.cn/article/2393",
        "港澳台招生",
        "hmt",
    ),
    OfficialSource(
        "international_entry_requirements_2026",
        "CUHK-Shenzhen 2026 Entry Requirements",
        "https://intladmissions.cuhk.edu.cn/en/taxonomy/term/149",
        "International Admissions",
        "international",
    ),
    OfficialSource(
        "international_who_can_apply",
        "CUHK-Shenzhen Who Can Apply",
        "https://intladmissions.cuhk.edu.cn/en/page/49",
        "International Admissions",
        "international",
    ),
    OfficialSource(
        "international_dates_2026",
        "CUHK-Shenzhen Application Rounds and Important Dates",
        "https://intladmissions.cuhk.edu.cn/en/page/190",
        "International Admissions",
        "international",
    ),
    OfficialSource(
        "international_scholarships",
        "CUHK-Shenzhen Scholarships and Work-Study Opportunities",
        "https://intladmissions.cuhk.edu.cn/en/page/18",
        "Scholarships",
        "international",
    ),
    OfficialSource(
        "programmes",
        "学院专业与特色项目",
        "https://admissions.cuhk.edu.cn/programmes",
        "专业介绍",
        "all",
    ),
    OfficialSource(
        "tuition_and_accommodation",
        "学费及住宿费",
        "https://admissions.cuhk.edu.cn/page/798",
        "费用",
        "all",
    ),
    OfficialSource(
        "internationalized_teaching",
        "国际化教学",
        "https://admissions.cuhk.edu.cn/page/67",
        "培养特色",
        "all",
    ),
]
