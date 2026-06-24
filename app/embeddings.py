from __future__ import annotations

import json
import urllib.error
import urllib.request


def ollama_embed(
    texts: list[str],
    base_url: str = "http://127.0.0.1:11434",
    model: str = "bge-m3:latest",
    timeout: int = 120,
    batch_size: int = 32,
) -> list[list[float]]:
    if not texts:
        return []

    embeddings: list[list[float]] = []
    for start in range(0, len(texts), batch_size):
        batch = texts[start : start + batch_size]
        payload = json.dumps({"model": model, "input": batch}).encode("utf-8")
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

        batch_embeddings = data.get("embeddings")
        if not isinstance(batch_embeddings, list):
            raise RuntimeError(f"Ollama response did not contain embeddings: {data}")
        embeddings.extend(batch_embeddings)
    return embeddings
