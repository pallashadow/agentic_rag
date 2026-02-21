def get_entry_prompt_and_format(
    question: str, 
    query_context: list[str], 
    agentic_config: dict,
    prompt_lang: str | None = None,
) -> tuple[str, dict]:
    """
    Build entry prompt and response format together.
    
    Returns:
        tuple: (prompt, response_format)
    """
    from lib.agentic.prompts.prompt_loader import render_prompt

    prompt_entry = render_prompt(
        "entry_prompt.yaml",
        prompt_lang=prompt_lang,
        question=question,
        query_context=query_context,
    )
    
    k = agentic_config.get("max_query_expand_k", 1)
    
    entry_schema = {
        "type": "object",
        "properties": {
            "expanded_queries": {
                "type": "array",
                "items": {"type": "string"},
                "minItems": 1,
                "maxItems": k
            },
            "query_type": {
                "type": "string",
                "enum": ["greeting", "insult", "unclear", "need_rag"]
            },
            "answer": {
                "type": "string",
            }
        },
        "required": ["query_type", "expanded_queries", "answer"]
    }

    entry_response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "entry_response_format",
            "schema": dict(entry_schema)
        }
    }
    
    return prompt_entry, entry_response_format

