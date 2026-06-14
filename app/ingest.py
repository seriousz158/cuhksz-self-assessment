from __future__ import annotations

import hashlib
import html
import json
import re
import subprocess
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from bs4 import BeautifulSoup

from app.config import KNOWLEDGE_DIR
from app.sources import OFFICIAL_SOURCES, OfficialSource


USER_AGENT = "Mozilla/5.0 (compatible; CUHKSZ-KB/1.0)"


def fetch_html(url: str, timeout: int = 30) -> str:
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            raw = response.read()
            encoding = response.headers.get_content_charset() or "utf-8"
            return raw.decode(encoding, errors="replace")
    except (urllib.error.URLError, TimeoutError, OSError):
        completed = subprocess.run(
            ["curl", "-L", "--max-time", str(timeout), "-A", USER_AGENT, url],
            capture_output=True,
            text=True,
            check=False,
        )
        if completed.returncode != 0 or not completed.stdout.strip():
            stderr = completed.stderr.strip() or f"curl exited with {completed.returncode}"
            raise RuntimeError(f"Failed to fetch {url}: {stderr}")
        return completed.stdout


def _clean_text(value: str) -> str:
    value = html.unescape(value)
    value = re.sub(r"\u00a0", " ", value)
    value = re.sub(r"[ \t]+", " ", value)
    value = re.sub(r"\n{3,}", "\n\n", value)
    return value.strip()


def html_to_markdown(raw_html: str, source: OfficialSource) -> str:
    soup = BeautifulSoup(raw_html, "html.parser")
    for tag in soup(["script", "style", "noscript", "svg", "canvas"]):
        tag.decompose()

    title = _clean_text(
        (soup.find("h1").get_text(" ", strip=True) if soup.find("h1") else "")
        or (soup.title.get_text(" ", strip=True) if soup.title else "")
        or source.title
    )

    content_root = (
        soup.find("main")
        or soup.find("article")
        or soup.find(class_=re.compile(r"(content|article|detail|main)", re.I))
        or soup.body
        or soup
    )

    lines: list[str] = [f"# {title}", ""]
    seen_blocks: set[str] = set()

    for element in content_root.find_all(["h1", "h2", "h3", "h4", "p", "li", "tr"], recursive=True):
        text = _clean_text(element.get_text(" ", strip=True))
        if not text or len(text) < 2:
            continue
        if text in seen_blocks:
            continue
        seen_blocks.add(text)

        if element.name in {"h1", "h2"}:
            prefix = "##"
        elif element.name in {"h3", "h4"}:
            prefix = "###"
        elif element.name == "li":
            prefix = "-"
        elif element.name == "tr":
            cells = [_clean_text(cell.get_text(" ", strip=True)) for cell in element.find_all(["th", "td"])]
            cells = [cell for cell in cells if cell]
            if not cells:
                continue
            text = " | ".join(cells)
            prefix = "-"
        else:
            prefix = ""

        lines.append(f"{prefix} {text}".strip())
        lines.append("")

    body = "\n".join(lines).strip()
    if len(seen_blocks) == 0:
        fallback = _clean_text(content_root.get_text("\n", strip=True))
        body = f"# {title}\n\n{fallback}"
    return body + "\n"


def _front_matter(source: OfficialSource, markdown: str) -> str:
    digest = hashlib.sha256(markdown.encode("utf-8")).hexdigest()
    metadata = {
        "source_id": source.source_id,
        "title": source.title,
        "url": source.url,
        "category": source.category,
        "applicant_path": source.applicant_path,
        "retrieved_at": datetime.now(timezone.utc).isoformat(),
        "content_sha256": digest,
    }
    lines = ["---"]
    lines.extend(f"{key}: {json.dumps(value, ensure_ascii=False)}" for key, value in metadata.items())
    lines.append("---")
    return "\n".join(lines) + "\n\n"


def ingest_sources(
    sources: Iterable[OfficialSource] = OFFICIAL_SOURCES,
    output_dir: Path = KNOWLEDGE_DIR,
) -> dict[str, object]:
    output_dir.mkdir(parents=True, exist_ok=True)
    results: list[dict[str, str]] = []
    failures: list[dict[str, str]] = []

    for source in sources:
        try:
            raw_html = fetch_html(source.url)
            markdown = html_to_markdown(raw_html, source)
            output_path = output_dir / f"{source.source_id}.md"
            output_path.write_text(_front_matter(source, markdown) + markdown, encoding="utf-8")
            results.append(
                {
                    "source_id": source.source_id,
                    "title": source.title,
                    "url": source.url,
                    "path": str(output_path),
                }
            )
        except Exception as exc:
            failures.append(
                {
                    "source_id": source.source_id,
                    "title": source.title,
                    "url": source.url,
                    "error": str(exc),
                }
            )
    return {"ingested": results, "failed": failures}
