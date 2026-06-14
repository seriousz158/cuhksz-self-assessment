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
