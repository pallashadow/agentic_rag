from __future__ import annotations

import re


_ZH_RE = re.compile(r"[\u4e00-\u9fff]")


def is_chinese_text(text: str) -> bool:
    return bool(_ZH_RE.search(text or ""))


def detect_query_lang(text: str) -> str:
    # Binary language policy: Chinese -> zh, otherwise -> en.
    return "zh" if is_chinese_text(text) else "en"

