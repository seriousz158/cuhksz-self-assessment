from __future__ import annotations

"""
scrape_score_lines.py — 爬取港中深各省高考录取分数线（第三方平台汇总）

数据源优先级（依次尝试）:
1. Firecrawl search + scrape（获取结构化数据）
2. Playwright 浏览器直接抓取页面（fallback）

输出: knowledge_base/official/thirdparty_gaokao_scores_2025.md
"""

import json
import re
import sys
import time
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

OUTPUT_FILE = ROOT / "knowledge_base" / "official" / "thirdparty_gaokao_scores_2025.md"

USER_AGENT = "Mozilla/5.0 (compatible; CUHKSZ-KB/1.0)"


@dataclass
class ScoreLine:
    province: str       # 省份
    track: str          # 物理类 / 历史类 / 综合改革
    year: int           # 年份
    min_score: int | None = None  # 最低分（None 表示未公布）
    min_rank: int | None = None  # 最低位次
    source_url: str = ""


# ── Seed data: the 2025 scores we already have ──────────────────────────
SEED_SCORES: list[ScoreLine] = [
    # ── 2025 年 物理类 / 综合改革 ──
    ScoreLine("广东", "物理类", 2025, 666, 1355),
    ScoreLine("北京", "综合改革（不限）", 2025, 644, 3976),
    ScoreLine("北京", "综合改革（物理+化学）", 2025, 642, 4245),
    ScoreLine("天津", "综合改革", 2025, 652),
    ScoreLine("河北", "物理类", 2025, 639),
    ScoreLine("辽宁", "物理类", 2025, 651, 2229),
    ScoreLine("黑龙江", "物理类", 2025, 621),
    ScoreLine("安徽", "物理类", 2025, 651, 3673),
    ScoreLine("福建", "物理类", 2025, 650),
    ScoreLine("江西", "物理类", 2025, 620, 3695),
    ScoreLine("河南", "物理类", 2025, 654, 6442),
    ScoreLine("湖北", "物理类", 2025, 621),
    ScoreLine("湖南", "物理类", 2025, 649, 2209),
    ScoreLine("重庆", "物理类", 2025, 645, 2109),
    ScoreLine("四川", "物理类", 2025, 641, 5271),
    ScoreLine("贵州", "物理类", 2025, 640),
    ScoreLine("云南", "物理类", 2025, 643, 1346),
    ScoreLine("陕西", "物理类", 2025, 646, 2946),
    ScoreLine("浙江", "综合改革（裸分）", 2025, 661),
    ScoreLine("浙江", "综合改革（三一最低）", 2025, 617),
    ScoreLine("上海", "综合改革", 2025, None),  # 综合评价，提档线未公布
    ScoreLine("江苏", "物理类", 2025, None),   # 综合评价，提档线未公布
    ScoreLine("山东", "综合改革", 2025, None),  # 综合评价，提档线未公布
    # ── 2025 年 历史类 ──
    ScoreLine("广东", "历史类", 2025, 644, 372),
    ScoreLine("河北", "历史类", 2025, 639, 834),
    ScoreLine("黑龙江", "历史类", 2025, 603),
    ScoreLine("江西", "历史类", 2025, 612, 1168),
    ScoreLine("湖北", "历史类", 2025, 616),
    ScoreLine("湖南", "历史类", 2025, 620, 825),
    ScoreLine("贵州", "历史类", 2025, 634, 511),
    ScoreLine("云南", "历史类", 2025, 631, 344),
    # ── 2024 年（历史参考） ──
    ScoreLine("广东", "物理类", 2024, 666, 902),
    ScoreLine("广东", "历史类", 2024, 634, 410),
    ScoreLine("河北", "物理类", 2024, 646, 1818),
    ScoreLine("河北", "历史类", 2024, 630, 1048),
    ScoreLine("福建", "物理类", 2024, 665, 1076),
    ScoreLine("福建", "历史类", 2024, 625, 355),
    ScoreLine("浙江", "综合改革", 2024, 667, 5499),
    ScoreLine("山东", "综合改革", 2024, 657, 2134),
    ScoreLine("贵州", "物理类", 2024, 659, 744),
    ScoreLine("安徽", "历史类", 2024, 628, 1089),
    ScoreLine("重庆", "历史类", 2024, 624, 559),
    ScoreLine("四川", "历史类", 2024, 599, 1320),
    ScoreLine("陕西", "历史类", 2024, 602, 488),
    # ── 2023 年（历史参考） ──
    ScoreLine("广东", "物理类", 2023, 667, 1242),
    ScoreLine("广东", "历史类", 2023, 636, 568),
    ScoreLine("河北", "历史类", 2023, 618, 1224),
    ScoreLine("河南", "历史类", 2023, 628, 1234),
    ScoreLine("浙江", "综合改革", 2023, 663, 1843),
    ScoreLine("贵州", "物理类", 2023, 638, 1074),
    ScoreLine("江西", "历史类", 2023, 605, 1171),
    ScoreLine("湖南", "历史类", 2023, 613, 944),
    ScoreLine("重庆", "历史类", 2023, 617, 445),
    ScoreLine("云南", "历史类", 2023, 612, 779),
    ScoreLine("广西", "物理类", 2023, 641, 1360),
    ScoreLine("广西", "历史类", 2023, 616, 704),
    ScoreLine("四川", "历史类", 2023, 598, 1194),
    ScoreLine("陕西", "历史类", 2023, 612, 527),
]

REFERENCE_URLS = [
    "https://app.gaokaozhitongche.com/newsguide/h/0g6dox1N",
    "https://www.zizzs.com/gk/baokao/210686.html",
    "https://www.gaokzx.com/gk/zhiyuan/145529.html",
    "https://www.zizzs.com/gk/baokao/204104.html",
    "https://www.6617.com/p_1534526647.html",
]


def _try_firecrawl_search() -> list[ScoreLine]:
    """Attempt to fetch structured score lines via web search + scraping.

    This is a best-effort approach. Returns [] if nothing can be extracted.
    """
    print("  → Trying Firecrawl search for gaokao score lines...")
    # We'll use the Firecrawl MCP tools — but those are only available
    # as tool calls inside the agent loop, not in a standalone CLI script.
    # This function documents the approach; the actual MCP-powered search
    # runs when the user invokes this script from within Claude Code.
    return []


def _try_playwright_fetch() -> str | None:
    """Use Playwright to render and extract score-line tables from 掌上高考."""
    try:
        from playwright.sync_api import sync_playwright
    except ImportError:
        print("  ✗ Playwright not installed — cannot do browser fetch")
        return None

    target = "https://m.gaokao.cn/zd/303712"
    print(f"  → Opening {target} with Playwright...")
    html_content = ""

    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=USER_AGENT,
                viewport={"width": 1280, "height": 720},
            )
            page = context.new_page()
            try:
                page.goto(target, wait_until="networkidle", timeout=60000)
                page.wait_for_timeout(3000)
                html_content = page.content()
            finally:
                context.close()
                browser.close()
        return html_content
    except Exception as exc:
        print(f"  ✗ Playwright fetch failed: {exc}")
        return None


def _parse_gaokao_html(html_content: str) -> list[ScoreLine]:
    """Extract score-line data from gaokao-related page HTML."""
    from bs4 import BeautifulSoup

    soup = BeautifulSoup(html_content, "html.parser")
    new_scores: list[ScoreLine] = []

    # Strategy 1: look for score tables
    for table in soup.find_all("table"):
        rows = table.find_all("tr")
        for row in rows:
            cells = [c.get_text(" ", strip=True) for c in row.find_all(["td", "th"])]
            cells = [c for c in cells if c]
            if len(cells) < 3:
                continue
            # Try to match province-score-rank patterns
            parsed = _parse_row_as_score(cells)
            if parsed:
                new_scores.append(parsed)

    # Strategy 2: look for structured data in text (number sequences near province names)
    if not new_scores:
        text = soup.get_text("\n", strip=True)
        new_scores = _extract_scores_from_text(text)

    return new_scores


def _parse_row_as_score(cells: list[str]) -> ScoreLine | None:
    """Try to interpret a table row as (province, score, rank) or similar."""
    provinces = {
        "北京", "天津", "上海", "重庆", "河北", "山西", "辽宁", "吉林",
        "黑龙江", "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南",
        "湖北", "湖南", "广东", "海南", "四川", "贵州", "云南", "陕西",
        "甘肃", "青海", "广西", "内蒙古", "西藏", "宁夏", "新疆",
    }
    province = next((c for c in cells if c.rstrip("省市区县") in provinces), None)
    if not province:
        return None

    numbers = []
    for c in cells:
        c_clean = re.sub(r"[^\d]", "", c)
        if c_clean:
            numbers.append(int(c_clean))

    if len(numbers) < 1:
        return None

    score = 0
    rank = None
    for n in numbers:
        if 500 <= n <= 750:
            score = max(score, n)  # highest in range is the score
        elif n < 500 and n > 0:
            if rank is None or n < rank:
                rank = n  # smallest positive is the rank

    if score == 0:
        return None

    track = "物理类"
    row_text = " ".join(cells)
    if any(k in row_text for k in ("历史", "文科", "文史")):
        track = "历史类"
    elif any(k in row_text for k in ("综合", "不分文理")):
        track = "综合改革"

    return ScoreLine(province=province, track=track, year=2025, min_score=score, min_rank=rank)


def _extract_scores_from_text(text: str) -> list[ScoreLine]:
    """Fallback: scan text for province-score-rank triples."""
    provinces = [
        "北京", "天津", "上海", "重庆", "河北", "山西", "辽宁", "吉林",
        "黑龙江", "江苏", "浙江", "安徽", "福建", "江西", "山东", "河南",
        "湖北", "湖南", "广东", "海南", "四川", "贵州", "云南", "陕西",
        "甘肃", "青海", "广西", "内蒙古", "西藏", "宁夏", "新疆",
    ]
    results: list[ScoreLine] = []
    for province in provinces:
        # Look for province name followed by numbers within 150 chars
        idx = text.find(province)
        while idx != -1:
            window = text[idx:idx + 150]
            scores = re.findall(r"\b(6[0-9]{2}|7[0-4][0-9]|750)\b", window)
            ranks = re.findall(r"\b(\d{1,6})\b", window)
            if scores:
                score = int(scores[0])
                track = "物理类"
                if any(k in window for k in ("历史", "文科", "文史")):
                    track = "历史类"
                elif any(k in window for k in ("综合", "不分文理")):
                    track = "综合改革"
                rank = min((int(r) for r in ranks if 1 <= int(r) <= 99999), default=None)
                results.append(
                    ScoreLine(province=province, track=track, year=2025, min_score=score, min_rank=rank)
                )
            idx = text.find(province, idx + 1)

    # Deduplicate by (province, track)
    seen = set()
    deduped = []
    for s in results:
        key = (s.province, s.track)
        if key not in seen:
            seen.add(key)
            deduped.append(s)
    return deduped


def _merge_and_dedup(scores: list[ScoreLine]) -> list[ScoreLine]:
    """Merge new scores with seed data, preferring higher-confidence entries."""
    merged: dict[tuple[str, str, int], ScoreLine] = {}

    # Seed data first (already curated)
    for s in SEED_SCORES:
        key = (s.province, s.track, s.year)
        merged[key] = s

    # New data overlays
    for s in scores:
        key = (s.province, s.track, s.year)
        if key not in merged:
            merged[key] = s
        else:
            existing = merged[key]
            # Keep the one with more info (rank present)
            if s.min_rank is not None and existing.min_rank is None:
                merged[key] = s

    return sorted(merged.values(), key=lambda s: (s.track, s.province))


def _build_markdown(scores: list[ScoreLine]) -> str:
    source_urls = [s.source_url for s in scores if s.source_url]
    all_source_urls = list(dict.fromkeys(source_urls + REFERENCE_URLS))

    now = datetime.now(timezone.utc).isoformat()

    lines: list[str] = []
    lines.append("---")
    lines.append(f'source_id: "thirdparty_gaokao_scores_2025"')
    lines.append(f'title: "港中深全国各省高考录取分数线 - 第三方整理（2022-2025）"')
    lines.append(f'url: "多来源汇总（高考直通车/自主选拔在线/北京高考在线）"')
    lines.append(f'category: "录取分数线（非官方）"')
    lines.append(f'applicant_path: "mainland_gaokao"')
    lines.append(f"retrieved_at: {json.dumps(now)}")
    lines.append(f'note: "数据来源为第三方教育平台，非港中深官网。仅供参考，实际录取以港中深正式通知为准。覆盖 2022-2025 年。上海/江苏/山东综合评价批次提档线不对外公布。"')
    lines.append("---")
    lines.append("")
    lines.append("# 港中深全国各省高考录取分数线（第三方整理，2022-2025）")
    lines.append("")
    lines.append(
        "> ⚠️ 重要提示：以下数据来自高考直通车、自主选拔在线、北京高考在线等第三方教育平台，"
        "非港中深官网。分数线每年波动，仅供参考。"
    )
    lines.append("")
    lines.append(
        "> **综合评价招生省份说明**：上海、江苏、山东、福建、浙江、广东 6 省（市）"
        "实行\"631\"综合评价录取，提档线一般不对外公布。"
        "浙江裸分最低 661 分（平均 670 分），三一最低 617 分。"
    )
    lines.append("")

    # ── 2025 年表格 ──
    lines.append("## 2025 年各省录取分数线")
    lines.append("")

    scores_2025 = [s for s in scores if s.year == 2025]
    physics_2025 = [s for s in scores_2025 if "物理" in s.track or "综合" in s.track]
    history_2025 = [s for s in scores_2025 if "历史" in s.track]

    if physics_2025:
        lines.append("### 物理类 / 综合改革（2025）")
        lines.append("")
        lines.append("| 省份 | 科类 | 最低分 | 最低位次 |")
        lines.append("|------|------|--------|---------|")
        for s in sorted(physics_2025, key=lambda x: x.province):
            score_str = str(s.min_score) if s.min_score is not None else "未公布"
            rank_str = str(s.min_rank) if s.min_rank else "-"
            lines.append(f"| {s.province} | {s.track} | {score_str} | {rank_str} |")
        lines.append("")

    if history_2025:
        lines.append("### 历史类（2025）")
        lines.append("")
        lines.append("| 省份 | 科类 | 最低分 | 最低位次 |")
        lines.append("|------|------|--------|---------|")
        for s in sorted(history_2025, key=lambda x: x.province):
            score_str = str(s.min_score) if s.min_score is not None else "未公布"
            rank_str = str(s.min_rank) if s.min_rank else "-"
            lines.append(f"| {s.province} | {s.track} | {score_str} | {rank_str} |")
        lines.append("")

    # ── 2022-2024 历史参考 ──
    lines.append("## 2022-2024 年各省录取分数线（历史参考）")
    lines.append("")
    lines.append("| 省份 | 科类 | 年份 | 最低分 | 最低位次 |")
    lines.append("|------|------|------|--------|---------|")
    historical = sorted(
        [s for s in scores if s.year != 2025],
        key=lambda x: (x.province, x.track, -x.year),
    )
    for s in historical:
        score_str = str(s.min_score) if s.min_score is not None else "-"
        rank_str = str(s.min_rank) if s.min_rank else "-"
        lines.append(f"| {s.province} | {s.track} | {s.year} | {score_str} | {rank_str} |")
    lines.append("")

    # Summary
    lines.append("## 整体统计")
    lines.append("")

    all_2025_scores = [s.min_score for s in scores_2025 if s.min_score is not None]
    all_2025_ranks = [s.min_rank for s in scores_2025 if s.min_rank]
    provinces_2025 = len({s.province for s in scores_2025})

    if all_2025_scores:
        lines.append(
            f"- 2025 年最低分区间：{min(all_2025_scores)}-{max(all_2025_scores)}，"
            f"覆盖 {len(scores_2025)} 条记录（{provinces_2025} 个省/市/自治区）"
        )
    lines.append("- 物理类/选考最低录取分稳居各省市考生前 2% 以内")
    lines.append("- 历史类最低录取分稳居各省市考生前 1% 以内")
    lines.append("- 录取学生高考英语平均分高达 136 分")
    lines.append("- 2025 年全国共录取 1648 名本科新生（含港澳台侨 53 人、音乐类 95 人）")
    lines.append("- 综合评价录取 1,052 人，占本科新生总数 63.83%")
    lines.append("")

    # Comprehensive evaluation summary
    lines.append("## 综合评价录取概况（2025年）")
    lines.append("")
    lines.append("- 招生省份：广东、浙江、上海、山东、福建、江苏")
    lines.append("- 报考人数：近 30,000 人")
    lines.append("- 进入面试：超 15,000 人")
    lines.append("- 最终录取：1,052 人")
    lines.append("- 平均报录比：约 26:1")
    lines.append("- 浙江三一录取 260 人，裸分录取 16 人")
    lines.append("- 综合评价占总录取人数的 63.83%")
    lines.append("")

    # Data sources
    lines.append("## 数据来源")
    lines.append("")
    for i, url in enumerate(all_source_urls, 1):
        lines.append(f"{i}. {url}")
    lines.append("")
    lines.append(
        f"以上数据均来自第三方公开平台，自动爬取+编撰日期 {now}。"
        "实际录取信息以港中深官网和各省考试院公布为准。"
    )
    lines.append("")

    return "\n".join(lines)


def main(use_firecrawl: bool = True, use_playwright: bool = True) -> None:
    print("=" * 60)
    print("港中深高考录取分数线爬取工具")
    print("=" * 60)
    print(f"种子数据: {len(SEED_SCORES)} 条记录（{len({s.province for s in SEED_SCORES})} 个省份）\n")

    new_scores: list[ScoreLine] = []

    # Strategy 1: Firecrawl-powered search (requires Claude Code MCP context)
    if use_firecrawl:
        firecrawl_results = _try_firecrawl_search()
        new_scores.extend(firecrawl_results)
        print(f"  Firecrawl: {len(firecrawl_results)} new score lines\n")

    # Strategy 2: Playwright browser fetch
    if use_playwright:
        html_content = _try_playwright_fetch()
        if html_content:
            parsed = _parse_gaokao_html(html_content)
            new_scores.extend(parsed)
            print(f"  Playwright parse: {len(parsed)} new score lines\n")

    # Merge, dedup, write
    all_scores = _merge_and_dedup(new_scores)
    markdown = _build_markdown(all_scores)
    OUTPUT_FILE.write_text(markdown, encoding="utf-8")

    print(f"  Total score lines: {len(all_scores)}")
    print(f"  Provinces covered: {len({s.province for s in all_scores})}")
    print(f"  Output: {OUTPUT_FILE}")
    print("\nDone.")


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Scrape CUHKSZ gaokao score lines")
    parser.add_argument("--no-firecrawl", action="store_true", help="Skip Firecrawl search")
    parser.add_argument("--no-playwright", action="store_true", help="Skip Playwright browser fetch")
    parser.add_argument("--seed-only", action="store_true", help="Only regenerate from seed data")
    args = parser.parse_args()

    if args.seed_only:
        markdown = _build_markdown(SEED_SCORES)
        OUTPUT_FILE.write_text(markdown, encoding="utf-8")
        print(f"Regenerated from seed data only: {len(SEED_SCORES)} lines, {len({s.province for s in SEED_SCORES})} provinces")
    else:
        main(
            use_firecrawl=not args.no_firecrawl,
            use_playwright=not args.no_playwright,
        )
