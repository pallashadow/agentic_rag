def build_validation_tool() -> dict:
    """Build function-calling schema for answer validation and refinement planning."""
    return {
        "type": "function",
        "function": {
            "name": "validate_and_refine",
            "description": "Validate answer quality and propose follow-up retrieval operations if needed",
            "parameters": {
                "type": "object",
                "properties": {
                    "type_state": {
                        "type": "string",
                        "enum": ["valid_answer", "refine_query"],
                        "description": "State indicating if answer is valid or needs refinement",
                    },
                    "search_ops": {
                        "type": "array",
                        "items": {
                            "type": "object",
                            "properties": {
                                "type": {
                                    "type": "string",
                                    "enum": ["search_general", "search_doc", "search_neighbour_chunks"],
                                    "description": "Type of search operation",
                                },
                                "query_list": {
                                    "type": "array",
                                    "items": {"type": "string"},
                                    "description": "List of queries for search_general type",
                                },
                                "doc_id": {
                                    "type": "string",
                                    "description": "Document ID for search_doc or search_neighbour_chunks",
                                },
                                "chunk_id": {
                                    "type": "string",
                                    "description": "Chunk ID for search_neighbour_chunks",
                                },
                                "distance": {
                                    "type": "integer",
                                    "description": "Distance for search_neighbour_chunks",
                                },
                            },
                        },
                        "description": "Legacy search operations for backward compatibility",
                    },
                    "valid_search_indices": {
                        "type": "array",
                        "items": {"type": "integer"},
                        "description": "Indices of valid search results (for valid_answer state)",
                    },
                },
                "required": ["type_state", "search_ops"],
            },
        },
    }


