import json


def get_agentic_prompt_and_format(
        question: str, 
        answer: str, 
        search_results: list[dict], 
        historical_search_ops: list[dict], 
        agentic_config: dict = None):
    """
    Build agentic prompt and response format together.
    
    Returns:
        tuple: (prompt, response_format)
    """
    agentic_config = agentic_config or {}
    search_results_txt = json.dumps(search_results, ensure_ascii=False)
    from lib.agentic.prompts.prompt_loader import render_prompt

    prompt_agentic = render_prompt(
        "agentic_prompt.yaml",
        question=question,
        historical_search_ops=historical_search_ops,
        search_results_txt=search_results_txt,
        answer=answer,
    )
    
    agentic_schema = {
        "type": "object",
        "properties": {
            "type_state": {
                "type": "string",
                "enum": ["valid_answer", "refine_query"]
            },
            "search_ops": {
                "type": "array",
                "items": {
                    "type": "object",
                    "properties": {
                        "type": {
                            "type": "string",
                            "enum": ["search_general", "search_doc", "search_neighbour_chunks"]
                        },
                        "query_list": {
                            "type": "array",
                            "items": {"type": "string"},
                            "description": "Required for search_general type",
                            "minItems": 1,
                            "maxItems": 3
                        },
                        "doc_id": {
                            "type": "string",
                            "description": "Required for search_neighbour_chunks type"
                        },
                        "chunk_id": {
                            "type": "string",
                            "description": "Required for search_neighbour_chunks type"
                        },
                        "distance": {
                            "type": "integer",
                            "description": "Required for search_neighbour_chunks type"
                        }
                    },
                    "required": ["type"]
                },
                "minItems": 0
            }
        },
        "required": ["type_state", "search_ops"]
    }
    agentic_response_format = {
        "type": "json_schema",
        "json_schema": {
            "name": "agentic_response_format",
            "schema": dict(agentic_schema)
        }
    }
    
    return prompt_agentic, agentic_response_format

