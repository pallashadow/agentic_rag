from __future__ import annotations

import os
from pathlib import Path
from typing import Any, Optional

import yaml


_PROJECT_ROOT = Path(__file__).resolve().parents[3]
_PROMPTS_DIR = _PROJECT_ROOT / "prompts"
_CACHE: dict[str, dict[str, Any]] = {}


class PromptTemplateError(RuntimeError):
    """Raised when prompt template loading or rendering fails."""


def _normalize_prompt_lang(lang: str) -> str:
    normalized = (lang or "zh").strip().lower()
    return normalized if normalized in {"zh", "en"} else "zh"


def _get_prompt_lang() -> str:
    return _normalize_prompt_lang(os.getenv("PROMPT_LANG", "zh"))


def _load_yaml_file(path: Path) -> dict[str, Any]:
    try:
        raw = path.read_text(encoding="utf-8")
    except FileNotFoundError as e:
        raise PromptTemplateError(
            f"Prompt template file not found: {path}. "
            f"Expected templates under: {_PROMPTS_DIR}"
        ) from e

    try:
        data = yaml.safe_load(raw)
    except Exception as e:  # noqa: BLE001 - surface YAML parsing errors clearly
        raise PromptTemplateError(f"Failed to parse YAML prompt template: {path}") from e

    if not isinstance(data, dict):
        raise PromptTemplateError(f"YAML prompt template must be a mapping/object: {path}")
    return data


def load_prompt_template(template_filename: str, prompt_lang: str | None = None) -> dict[str, Any]:
    """
    Load a YAML prompt template.

    Search order:
    - `<project_root>/prompts/<PROMPT_LANG>/`
    - `<project_root>/prompts/zh/` (fallback)
    - `<project_root>/prompts/` (legacy fallback)

    Args:
        template_filename: e.g. "entry_prompt.yaml"

    Returns:
        dict: Parsed YAML content.
    """
    resolved_prompt_lang = _normalize_prompt_lang(prompt_lang) if prompt_lang else _get_prompt_lang()
    cache_key = f"{resolved_prompt_lang}:{template_filename}"
    if cache_key not in _CACHE:
        search_dirs = (
            _PROMPTS_DIR / resolved_prompt_lang,
            _PROMPTS_DIR / "zh",
            _PROMPTS_DIR,
        )
        found_path: Optional[Path] = None
        for base in search_dirs:
            candidate = base / template_filename
            if candidate.exists():
                found_path = candidate
                break
        if found_path is None:
            raise PromptTemplateError(
                f"Prompt template file not found: {template_filename}. "
                f"Searched: {', '.join(str(d) for d in search_dirs)}"
            )
        _CACHE[cache_key] = _load_yaml_file(found_path)
    return _CACHE[cache_key]


def render_prompt(template_filename: str, prompt_lang: str | None = None, **variables: Any) -> str:
    """
    Render the `body.template` field of the YAML using Python `str.format`.

    NOTE:
    - Keep placeholders like `{question}` in the YAML template.
    - Ensure any literal braces in templates are escaped as `{{` and `}}`.
    """
    tmpl = load_prompt_template(template_filename, prompt_lang=prompt_lang)
    body = tmpl.get("body", {})
    template = body.get("template")
    if not isinstance(template, str) or not template.strip():
        raise PromptTemplateError(
            f"Missing or invalid `body.template` in YAML prompt template: {template_filename}"
        )

    try:
        return template.format(**variables)
    except KeyError as e:
        raise PromptTemplateError(
            f"Missing template variable {e} when rendering: {template_filename}"
        ) from e


