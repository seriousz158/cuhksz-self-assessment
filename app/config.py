from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent
KNOWLEDGE_DIR = BASE_DIR / "knowledge_base" / "official"
INDEX_DIR = BASE_DIR / "data" / "index"
HISTORY_DIR = BASE_DIR / "data" / "history"
HISTORY_FILE = HISTORY_DIR / "self_assessments.jsonl"


def load_env_file(path: Path | None = None) -> None:
    env_path = path or BASE_DIR / ".env"
    if not env_path.exists():
        return
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


@dataclass(frozen=True)
class Settings:
    openai_base_url: str
    openai_api_key: str
    model_name: str
    ollama_base_url: str
    embedding_model: str
    chunk_size: int
    chunk_overlap: int
    retrieval_top_k: int
    request_timeout: int

    @property
    def llm_configured(self) -> bool:
        return bool(self.openai_api_key and self.model_name)


def get_settings() -> Settings:
    load_env_file()
    return Settings(
        openai_base_url=os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
        openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        model_name=os.getenv("MODEL_NAME", ""),
        ollama_base_url=os.getenv("OLLAMA_BASE_URL", "http://127.0.0.1:11434").rstrip("/"),
        embedding_model=os.getenv("EMBEDDING_MODEL", "bge-m3:latest"),
        chunk_size=int(os.getenv("CHUNK_SIZE", "900")),
        chunk_overlap=int(os.getenv("CHUNK_OVERLAP", "160")),
        retrieval_top_k=int(os.getenv("RETRIEVAL_TOP_K", "16")),
        request_timeout=int(os.getenv("REQUEST_TIMEOUT", "120")),
    )
