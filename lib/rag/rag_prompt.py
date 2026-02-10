import json


def _load_rag_prompt_config() -> dict:
    """
    Load RAG prompt configuration from YAML.

    Motivation: keep all non-English prompt text out of Python source and centralize prompts under
    `<project_root>/prompts/`.
    """
    from lib.agentic.prompts.prompt_loader import load_prompt_template

    tmpl = load_prompt_template("rag.yaml")
    body = tmpl.get("body", {})
    if not isinstance(body, dict):
        body = {}
    return body


def _get_default_prompt_before_after() -> tuple[str, str]:
    body = _load_rag_prompt_config()
    prompt_before = body.get("prompt_before", "")
    prompt_after = body.get("prompt_after", "")

    if not isinstance(prompt_before, str) or not prompt_before.strip():
        raise ValueError("Invalid rag.yaml: missing non-empty body.prompt_before")
    if not isinstance(prompt_after, str):
        prompt_after = ""
    return prompt_before, prompt_after


PROMPT_BASE = dict(zip(("prompt1", "prompt2"), _get_default_prompt_before_after()))


def build_rag_prompt(query: str, 
                     search_results: list[dict], 
                     query_context: list[str]=[], 
                     prompt_before: str=None, 
                     prompt_after: str=None
    ) -> str:
    search_results_txt = json.dumps(search_results, ensure_ascii=False)
    query_context_txt = json.dumps(query_context, ensure_ascii=False)

    body = _load_rag_prompt_config()
    topic_line_template = body.get("topic_line_template", "{question}\n")
    history_line_template = body.get("history_line_template", "{query_context_txt}\n")
    refs_line_template = body.get("refs_line_template", "{search_results_txt}\n")

    if not prompt_before:
        prompt_before = PROMPT_BASE["prompt1"]
    if not prompt_after:
        prompt_after = PROMPT_BASE["prompt2"]

    parts: list[str] = [prompt_before]
    if isinstance(topic_line_template, str):
        parts.append(topic_line_template.format(question=query))
    if query_context and isinstance(history_line_template, str):
        parts.append(history_line_template.format(query_context_txt=query_context_txt))
    if isinstance(refs_line_template, str):
        parts.append(refs_line_template.format(search_results_txt=search_results_txt))
    parts.append(prompt_after)
    return "\n".join(p for p in parts if isinstance(p, str) and p != "")

