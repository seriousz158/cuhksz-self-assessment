from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.ingest import fetch_html_with_browser, html_to_markdown, _front_matter
from app.sources import OFFICIAL_SOURCES


def main() -> None:
    spa_sources = [s for s in OFFICIAL_SOURCES if s.js_render]
    if not spa_sources:
        print("No js_render=True sources found. Nothing to do.")
        return

    print(f"Rescraping {len(spa_sources)} SPA sources with Playwright browser:\n")
    results, failures = [], []

    for source in spa_sources:
        print(f"  [{source.source_id}] {source.title}")
        print(f"       URL: {source.url}")
        try:
            raw_html = fetch_html_with_browser(source.url)
            markdown = html_to_markdown(raw_html, source)
            output_path = ROOT / "knowledge_base" / "official" / f"{source.source_id}.md"
            output_path.write_text(
                _front_matter(source, markdown) + markdown, encoding="utf-8"
            )
            lines = len(markdown.splitlines())
            print(f"       OK  — {lines} lines written to {output_path.name}\n")
            results.append(
                {
                    "source_id": source.source_id,
                    "title": source.title,
                    "lines": lines,
                    "path": str(output_path),
                }
            )
        except Exception as exc:
            print(f"       FAIL — {exc}\n")
            failures.append(
                {"source_id": source.source_id, "url": source.url, "error": str(exc)}
            )

    print(
        json.dumps(
            {"ingested": len(results), "failed": len(failures), "sources": results, "failures": failures},
            ensure_ascii=False,
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
