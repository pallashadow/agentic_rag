from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from lib.agentic.config import AgentState
from lib.skills.registry import SkillRegistry
from lib.app_logger import get_logger

logger = get_logger(__name__)


def _legacy_op_to_skill_calls(search_ops: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Convert legacy `search_ops` into skill-like tool calls."""
    planned_calls: list[dict[str, Any]] = []

    for op in search_ops:
        search_type = op.get("type")
        if search_type == "search_general":
            args = {
                "query_list": op.get("query_list", []),
            }
            if "top_k" in op:
                args["top_k"] = op["top_k"]
            planned_calls.append(
                {
                    "id": f"legacy_general_{len(planned_calls)}",
                    "function": {"name": "general_search", "arguments": json.dumps(args, ensure_ascii=False)},
                }
            )
        elif search_type == "search_doc":
            doc_id = op.get("doc_id")
            query_list = op.get("query_list", [])
            if not doc_id or not query_list:
                continue
            for query in query_list:
                args = {"query": query, "doc_id": doc_id}
                if "top_k" in op:
                    args["top_k"] = op["top_k"]
                planned_calls.append(
                    {
                        "id": f"legacy_doc_{len(planned_calls)}",
                        "function": {"name": "document_search", "arguments": json.dumps(args, ensure_ascii=False)},
                    }
                )
        elif search_type == "search_neighbour_chunks":
            doc_id = op.get("doc_id")
            chunk_id = op.get("chunk_id")
            if not doc_id or not chunk_id:
                continue
            args = {
                "doc_id": doc_id,
                "chunk_id": chunk_id,
                "distance": op.get("distance", 1),
            }
            planned_calls.append(
                {
                    "id": f"legacy_neighbour_{len(planned_calls)}",
                    "function": {"name": "neighbour_search", "arguments": json.dumps(args, ensure_ascii=False)},
                }
            )

    return planned_calls


async def rag_search_node(state: AgentState, skill_registry: SkillRegistry) -> AgentState:
    """
    Second node (non-LLM): Perform RAG search with expanded queries.
    
    This node executes the actual search operation using the expanded queries generated
    in previous nodes. It increments the search_count to track how many search iterations
    have been performed, which is used to prevent infinite loops in the RAG flow.
    
    The search results are stored in state for use by subsequent LLM nodes that generate
    answers or validate the quality of retrieved information.
    """
    search_ops = state.get("search_ops")
    planned_skill_calls = state.get("planned_skill_calls", [])
    historical_search_ops = state.get("historical_search_ops", [])
    skill_errors = state.get("skill_errors", [])

    """
    # Backward compatibility: convert legacy search_ops into planned skill calls.
    if not planned_skill_calls:
        if search_ops is None:
            search_ops = [{"type": "search_general", "query_list": [state.get("question", "")]}]
        planned_skill_calls = _legacy_op_to_skill_calls(search_ops)
    """

    # Keep traceability of what this execution node consumed.
    historical_search_ops = historical_search_ops + planned_skill_calls

    # Process each skill call and combine results
    all_results = []
    for tool_call in planned_skill_calls:
        function = tool_call.get("function", {})
        skill_name = function.get("name")
        arguments_json = function.get("arguments", "{}")

        if not skill_name:
            logger.warning("tool_call missing function.name, skipping")
            skill_errors.append(
                {
                    "skill_name": "",
                    "code": "invalid_tool_call",
                    "message": "Missing function.name",
                    "arguments": arguments_json,
                }
            )
            continue

        try:
            skill = skill_registry.get(skill_name)
        except ValueError as e:
            logger.warning(f"Unknown skill '{skill_name}', skipping: {e}")
            skill_errors.append(
                {
                    "skill_name": skill_name,
                    "code": "skill_not_found",
                    "message": str(e),
                    "arguments": arguments_json,
                }
            )
            continue

        try:
            input_data = skill.input_model.model_validate_json(arguments_json)
        except ValidationError as e:
            logger.warning(f"Invalid arguments for skill '{skill_name}', skipping: {e}")
            skill_errors.append(
                {
                    "skill_name": skill_name,
                    "code": "invalid_arguments",
                    "message": str(e),
                    "arguments": arguments_json,
                }
            )
            continue

        try:
            output = await skill.execute(input_data, state=state)
            all_results.extend(output.model_dump().get("results", []))
        except Exception as e:  # noqa: BLE001 - keep workflow resilient per call
            logger.warning(f"Skill execution failed for '{skill_name}', skipping: {e}")
            skill_errors.append(
                {
                    "skill_name": skill_name,
                    "code": "skill_execution_failed",
                    "message": str(e),
                    "arguments": arguments_json,
                }
            )

    # Increment search count to track RAG search iterations
    search_count = state.get("search_count", 0) + 1
    
    return {
        **state,
        "search_results": all_results,
        "search_count": search_count,
        "historical_search_ops": historical_search_ops,
        "planned_skill_calls": [],
        "skill_errors": skill_errors,
    }

