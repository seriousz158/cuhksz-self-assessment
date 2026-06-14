from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from app.ingest import ingest_sources


def main() -> None:
    results = ingest_sources()
    print(json.dumps({"ingested": len(results), "sources": results}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
