import json


def _load_rag_prompt_config() -> dict:
    """Load RAG prompt config for agentic flow from shared rag.yaml."""
    from lib.agentic.prompts.prompt_loader import load_prompt_template

    tmpl = load_prompt_template("rag.yaml")
    body = tmpl.get("body", {})
    if not isinstance(body, dict):
        body = {}
    return body


def _build_rag_prompt(question: str, search_results: list[dict]) -> str:
    """Build the RAG answer prompt without depending on lib.rag."""
    body = _load_rag_prompt_config()
    prompt_before = body.get("prompt_before", "")
    prompt_after = body.get("prompt_after", "")
    topic_line_template = body.get("topic_line_template", "{question}\n")
    refs_line_template = body.get("refs_line_template", "{search_results_txt}\n")
    search_results_txt = json.dumps(search_results, ensure_ascii=False)

    parts: list[str] = []
    if isinstance(prompt_before, str) and prompt_before:
        parts.append(prompt_before)
    if isinstance(topic_line_template, str):
        parts.append(topic_line_template.format(question=question))
    if isinstance(refs_line_template, str):
        parts.append(refs_line_template.format(search_results_txt=search_results_txt))
    if isinstance(prompt_after, str) and prompt_after:
        parts.append(prompt_after)
    return "\n".join(parts)


def get_rag_prompt_and_format(question, search_results, agentic_config=None):
    """
    Build RAG prompt and response format together.
    
    Returns:
        tuple: (prompt, response_format)
    """
    rag_prompt = _build_rag_prompt(question, search_results)
    
    rag_schema = {
        "type": "object",
        "properties": {
            "answer": {
                "type": "string",
            },
            "valid_search_indices": {
                "type": "array",
                "items": {"type": "integer"},
                "description": "List of search index values that are mentioned in the answer"
            },
        },
        "required": ["answer", "valid_search_indices"]
    }
    rag_response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "rag_response_format",
            "schema": dict(rag_schema)
        }
    }
    
    return rag_prompt, rag_response_format

