from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path


_MAPPING_PATH = Path(__file__).resolve().parent / "index_mapping.json"


@lru_cache(maxsize=1)
def _load_mapping() -> dict[str, dict[str, str]]:
    raw = _MAPPING_PATH.read_text(encoding="utf-8")
    data = json.loads(raw)
    if not isinstance(data, dict):
        return {}
    return data


def get_index_meta(chunk_index: str) -> dict[str, str]:
    mapping = _load_mapping()
    item = mapping.get(chunk_index, {})
    title_index = item.get("title_index") or f"{chunk_index}_titles"
    doc_lang = item.get("doc_lang") or "zh"
    return {
        "chunk_index": chunk_index,
        "title_index": title_index,
        "doc_lang": doc_lang,
    }

