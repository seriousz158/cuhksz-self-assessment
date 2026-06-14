from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.config import HISTORY_FILE


def append_history(record: dict[str, Any], history_file: Path = HISTORY_FILE) -> None:
    history_file.parent.mkdir(parents=True, exist_ok=True)
    with history_file.open("a", encoding="utf-8") as file:
        file.write(json.dumps(record, ensure_ascii=False) + "\n")


def read_history(limit: int = 50, history_file: Path = HISTORY_FILE) -> list[dict[str, Any]]:
    if not history_file.exists():
        return []
    rows = []
    for line in history_file.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            rows.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return list(reversed(rows[-limit:]))


def clear_history_with_double_confirmation(
    confirm_first: bool,
    confirm_second: bool,
    phrase: str,
    history_file: Path = HISTORY_FILE,
) -> dict[str, str]:
    expected_phrase = "我确认清空历史记录"
    if not (confirm_first and confirm_second and phrase.strip() == expected_phrase):
        return {
            "status": "refused",
            "message": f"未清空。需要两次确认，并输入：{expected_phrase}",
        }
    history_file.parent.mkdir(parents=True, exist_ok=True)
    history_file.write_text("", encoding="utf-8")
    return {"status": "cleared", "message": "历史记录已清空。"}
