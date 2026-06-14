from __future__ import annotations

import json
import urllib.error
import urllib.request


def ollama_embed(
    texts: list[str],
    base_url: str = "http://127.0.0.1:11434",
    model: str = "bge-m3:latest",
    timeout: int = 120,
) -> list[list[float]]:
    if not texts:
        return []

    payload = json.dumps({"model": model, "input": texts}).encode("utf-8")
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/api/embed",
        data=payload,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            data = json.loads(response.read().decode("utf-8"))
    except (urllib.error.URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(
            f"Cannot reach Ollama embedding endpoint at {base_url}. "
            f"Start Ollama and ensure model {model!r} is installed."
        ) from exc

    embeddings = data.get("embeddings")
    if not isinstance(embeddings, list):
        raise RuntimeError(f"Ollama response did not contain embeddings: {data}")
    return embeddings
