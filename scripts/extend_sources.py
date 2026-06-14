from __future__ import annotations
import json, sys
from pathlib import Path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from app.ingest import fetch_html, html_to_markdown, _front_matter
from app.config import KNOWLEDGE_DIR
from app.sources import OfficialSource

EXTENDED = [
    OfficialSource("scholarship_hmt_2025","香港中文大学（深圳）2025年港澳台新生入学奖学金实施办法","https://admissions.cuhk.edu.cn/article/2145","奖学金","hmt"),
    OfficialSource("scholarship_sports_2025","香港中文大学（深圳）2025年新生运动特长奖学金实施办法","https://admissions.cuhk.edu.cn/article/2168","奖学金","all"),
    OfficialSource("scholarship_academic_2025","香港中文大学（深圳）2025年新生学科特长奖学金实施办法","https://admissions.cuhk.edu.cn/article/2169","奖学金","all"),
    OfficialSource("scholarship_bowen_2025","香港中文大学（深圳）2025年新生入学博文奖学金申请办法","https://admissions.cuhk.edu.cn/article/2170","奖学金","mainland_gaokao"),
    OfficialSource("scholarship_music_2025","香港中文大学（深圳）2025年音乐类新生入学奖学金实施办法","https://admissions.cuhk.edu.cn/article/2192","奖学金","comprehensive_eval"),
    OfficialSource("comprehensive_eval_arrangement_2026","香港中文大学（深圳）2026年综合评价入学测试安排","https://admissions.cuhk.edu.cn/article/2400","综合评价","comprehensive_eval"),
    OfficialSource("admissions_contacts_2026","香港中文大学（深圳）2026年各招生组联系方式","https://admissions.cuhk.edu.cn/article/2402","联系方式","all"),
    OfficialSource("university_overview","大学概览","https://admissions.cuhk.edu.cn/page/29","大学概况","all"),
    OfficialSource("college_system","书院制度","https://admissions.cuhk.edu.cn/page/30","书院","all"),
    OfficialSource("scholarship_overview","奖助学金","https://admissions.cuhk.edu.cn/page/37","奖学金","all"),
    OfficialSource("faq_2025","2025年本科招生问答","https://admissions.cuhk.edu.cn/taxonomy/term/154","常见问题","all"),
    OfficialSource("music_admissions","音乐类招生","https://admissions.cuhk.edu.cn/page/1476","音乐类招生","comprehensive_eval"),
    # ── 专业详情页（每个专业的课程介绍、培养目标、师资等） ──
    OfficialSource("programme_marketing","市场营销专业","https://admissions.cuhk.edu.cn/page/1443","专业介绍","all"),
    OfficialSource("programme_intl_business","国际商务专业","https://admissions.cuhk.edu.cn/page/1438","专业介绍","all"),
    OfficialSource("programme_economics","经济学专业","https://admissions.cuhk.edu.cn/page/1442","专业介绍","all"),
    OfficialSource("programme_finance","金融学专业","https://admissions.cuhk.edu.cn/page/1441","专业介绍","all"),
    OfficialSource("programme_accounting","会计学专业","https://admissions.cuhk.edu.cn/page/1439","专业介绍","all"),
    OfficialSource("programme_bigdata_mgmt","大数据管理与应用专业","https://admissions.cuhk.edu.cn/page/2193","专业介绍","all"),
    OfficialSource("programme_materials","材料科学与工程专业","https://admissions.cuhk.edu.cn/page/1534","专业介绍","all"),
    OfficialSource("programme_chemistry","化学专业","https://admissions.cuhk.edu.cn/page/1445","专业介绍","all"),
    OfficialSource("programme_physics","物理学专业","https://admissions.cuhk.edu.cn/page/1686","专业介绍","all"),
    OfficialSource("programme_new_energy","新能源科学与工程专业","https://admissions.cuhk.edu.cn/page/1448","专业介绍","all"),
    OfficialSource("programme_ece","电子与计算机工程专业","https://admissions.cuhk.edu.cn/page/1444","专业介绍","all"),
    OfficialSource("programme_math","数学与应用数学专业","https://admissions.cuhk.edu.cn/page/1447","专业介绍","all"),
    OfficialSource("programme_applied_psych","应用心理学专业","https://admissions.cuhk.edu.cn/page/1452","专业介绍","all"),
    OfficialSource("programme_urban_mgmt","城市管理专业","https://admissions.cuhk.edu.cn/page/2129","专业介绍","all"),
    OfficialSource("programme_intl_org","国际组织与全球治理专业","https://admissions.cuhk.edu.cn/page/2130","专业介绍","all"),
    OfficialSource("programme_statistics","统计学专业","https://admissions.cuhk.edu.cn/page/1459","专业介绍","all"),
    OfficialSource("programme_cs","计算机科学与技术专业","https://admissions.cuhk.edu.cn/page/1457","专业介绍","all"),
    OfficialSource("programme_ds","数据科学与大数据技术专业","https://admissions.cuhk.edu.cn/page/1458","专业介绍","all"),
    OfficialSource("programme_music_perf","音乐表演专业","https://admissions.cuhk.edu.cn/page/1461","专业介绍","all"),
    OfficialSource("programme_musicology","音乐学专业","https://admissions.cuhk.edu.cn/page/1537","专业介绍","all"),
    OfficialSource("programme_composition","作曲与作曲技术理论专业","https://admissions.cuhk.edu.cn/page/1538","专业介绍","all"),
    OfficialSource("programme_clinical_med","临床医学专业","https://admissions.cuhk.edu.cn/page/1460","专业介绍","all"),
    OfficialSource("programme_bioinfo","生物信息学专业","https://admissions.cuhk.edu.cn/page/1454","专业介绍","all"),
    OfficialSource("programme_bme","生物医学工程专业","https://admissions.cuhk.edu.cn/page/1455","专业介绍","all"),
    OfficialSource("programme_bioscience","生物科学专业","https://admissions.cuhk.edu.cn/page/1453","专业介绍","all"),
    OfficialSource("programme_pharmacy","药学专业","https://admissions.cuhk.edu.cn/page/1456","专业介绍","all"),
    OfficialSource("programme_fin_eng","金融工程专业","https://admissions.cuhk.edu.cn/page/1440","专业介绍","all"),
    # Off-site programme pages
    OfficialSource("programme_ai","人工智能专业","https://sai.cuhk.edu.cn/page/47","专业介绍","all"),
    OfficialSource("programme_dual_data","跨学科数据分析+X双主修项目","https://ccco.cuhk.edu.cn/node/60","专业介绍","all"),
    OfficialSource("programme_dual_aerospace","航天科学与地球信息学+X双主修项目","https://ccco.cuhk.edu.cn/node/36","专业介绍","all"),
    OfficialSource("programme_dual_materials","材料科学与工程学+X双主修项目","https://ccco.cuhk.edu.cn/node/273","专业介绍","all"),
]

def main():
    KNOWLEDGE_DIR.mkdir(parents=True, exist_ok=True)
    results, failures = [], []
    for source in EXTENDED:
        try:
            raw_html = fetch_html(source.url)
            markdown = html_to_markdown(raw_html, source)
            output_path = KNOWLEDGE_DIR / f"{source.source_id}.md"
            output_path.write_text(_front_matter(source, markdown) + markdown, encoding="utf-8")
            results.append({"source_id": source.source_id, "title": source.title, "url": source.url, "path": str(output_path)})
        except Exception as exc:
            failures.append({"source_id": source.source_id, "url": source.url, "error": str(exc)})
    print(json.dumps({"ingested": len(results), "failed": len(failures), "sources": results, "failures": failures}, ensure_ascii=False, indent=2))

if __name__ == "__main__":
    main()
