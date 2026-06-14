from __future__ import annotations

import json
import re
from dataclasses import dataclass, asdict
from pathlib import Path

from app.config import KNOWLEDGE_DIR


FRONT_MATTER_RE = re.compile(r"^---\n(.*?)\n---\n\n?", re.S)


@dataclass
class Document:
    path: str
    title: str
    source_id: str
    url: str
    category: str
    applicant_path: str
    text: str


@dataclass
class Chunk:
    chunk_id: int
    text: str
    source_id: str
    title: str
    url: str
    category: str
    applicant_path: str
    path: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def parse_front_matter(text: str) -> tuple[dict[str, str], str]:
    match = FRONT_MATTER_RE.match(text)
    if not match:
        return {}, text

    metadata: dict[str, str] = {}
    for line in match.group(1).splitlines():
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        key = key.strip()
        value = value.strip()
        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            parsed = value.strip('"').strip("'")
        metadata[key] = str(parsed)
    return metadata, text[match.end() :]


def load_documents(directory: Path = KNOWLEDGE_DIR) -> list[Document]:
    if not directory.exists():
        return []

    documents: list[Document] = []
    for path in sorted(directory.rglob("*")):
        if path.suffix.lower() not in {".md", ".txt"} or not path.is_file():
            continue
        raw_text = path.read_text(encoding="utf-8")
        metadata, body = parse_front_matter(raw_text)
        fallback_title = path.stem.replace("_", " ")
        title = metadata.get("title") or _extract_title(body) or fallback_title
        documents.append(
            Document(
                path=str(path),
                title=title,
                source_id=metadata.get("source_id", path.stem),
                url=metadata.get("url", ""),
                category=metadata.get("category", "official"),
                applicant_path=metadata.get("applicant_path", "all"),
                text=body.strip(),
            )
        )
    return documents


def _extract_title(text: str) -> str:
    for line in text.splitlines():
        line = line.strip()
        if line.startswith("#"):
            return line.lstrip("#").strip()
    return ""


def split_text(text: str, chunk_size: int = 900, chunk_overlap: int = 160) -> list[str]:
    normalized = re.sub(r"\n{3,}", "\n\n", text).strip()
    if not normalized:
        return []

    paragraphs = re.split(r"(?<=[。！？.!?])\s+|\n{2,}", normalized)
    chunks: list[str] = []
    current = ""

    for paragraph in paragraphs:
        paragraph = paragraph.strip()
        if not paragraph:
            continue
        if len(paragraph) > chunk_size:
            if current:
                chunks.append(current.strip())
                current = ""
            for start in range(0, len(paragraph), max(1, chunk_size - chunk_overlap)):
                piece = paragraph[start : start + chunk_size].strip()
                if piece:
                    chunks.append(piece)
            continue
        if len(current) + len(paragraph) + 2 <= chunk_size:
            current = f"{current}\n\n{paragraph}".strip()
        else:
            if current:
                chunks.append(current.strip())
            overlap = current[-chunk_overlap:].strip() if chunk_overlap and current else ""
            current = f"{overlap}\n\n{paragraph}".strip() if overlap else paragraph

    if current:
        chunks.append(current.strip())

    return [chunk for chunk in chunks if chunk]


def build_chunks(
    documents: list[Document],
    chunk_size: int = 900,
    chunk_overlap: int = 160,
) -> list[Chunk]:
    chunks: list[Chunk] = []
    for document in documents:
        for text in split_text(document.text, chunk_size=chunk_size, chunk_overlap=chunk_overlap):
            chunks.append(
                Chunk(
                    chunk_id=len(chunks),
                    text=text,
                    source_id=document.source_id,
                    title=document.title,
                    url=document.url,
                    category=document.category,
                    applicant_path=document.applicant_path,
                    path=document.path,
                )
            )
    return chunks
