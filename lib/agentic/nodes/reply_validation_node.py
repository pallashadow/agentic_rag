from lib.agentic.config import AgentState
from lib.agentic.prompts import get_agentic_prompt_and_format
from lib.llm.litellm_api import call_llm_with_fallback, call_llm_with_tools
from lib.agentic.prompts.prompt_loader import render_prompt
from lib.agentic.tools.validation_tool import build_validation_tool
from lib.app_logger import get_logger
from lib.skills.registry import SkillRegistry
import json

logger = get_logger(__name__)


def _legacy_search_ops_to_planned_calls(search_ops: list[dict]) -> list[dict]:
    """Convert legacy search_ops to skill tool calls for execution node."""
    planned_calls = []
    for op in search_ops:
        search_type = op.get("type")
        if search_type == "search_general":
            args = {"query_list": op.get("query_list", [])}
            if "top_k" in op:
                args["top_k"] = op["top_k"]
            planned_calls.append(
                {
                    "id": f"legacy_general_{len(planned_calls)}",
                    "function": {
                        "name": "general_search",
                        "arguments": json.dumps(args, ensure_ascii=False),
                    },
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
                        "function": {
                            "name": "document_search",
                            "arguments": json.dumps(args, ensure_ascii=False),
                        },
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
                    "function": {
                        "name": "neighbour_search",
                        "arguments": json.dumps(args, ensure_ascii=False),
                    },
                }
            )
    return planned_calls


async def reply_validation_node(state: AgentState, skill_registry: SkillRegistry) -> AgentState:
    """
    Fourth node (third LLM node): Validate answer quality and refine queries if needed.
    
    This node evaluates whether the generated answer adequately addresses the user's query.
    It uses structured output to determine one of two states:
    - "valid_answer": The current answer is sufficient, workflow can proceed to final answer
    - "refine_query": The answer needs improvement, generate refined queries for another search iteration
    
    The node also enforces a maximum search count limit to prevent infinite loops. If the limit
    is exceeded, it accepts the current answer regardless of validation result.
    
    When refining queries, it filters out invalid search results based on LLM feedback and
    updates historical queries to track all search attempts.
    """
    agentic_config = state.get("agentic_config", {})
    max_iter = agentic_config.get("max_iter", 3)
    search_count = state.get("search_count", 0)
    search_results = state.get("search_results", [])
    planned_skill_calls = []
    
    # Check if maximum search iterations have been reached
    exceeded_limit = search_count >= max_iter
    
    if not exceeded_limit:
        # Use LLM to evaluate answer quality and determine next action
        question = state.get("question", "")
        answer = state.get("answer", "")
        search_results = state.get("search_results", [])
        historical_search_ops = state.get("historical_search_ops", [])
        
        # Build prompt using existing template
        search_results_txt = json.dumps(search_results, ensure_ascii=False)
        prompt_agentic = render_prompt(
            "agentic_prompt.yaml",
            question=question,
            historical_search_ops=historical_search_ops,
            search_results_txt=search_results_txt,
            answer=answer,
        )
        prompt_agentic += "\n\n请使用 validate_and_refine 工具进行评估。"
        
        # Define validation tool and skill tools.
        validation_tool = build_validation_tool()
        tools = [validation_tool] + skill_registry.get_all_tool_schemas()
        
        try:
            # Call LLM with function calling
            response = await call_llm_with_tools(
                prompt_agentic,
                tools=tools,
                model_name="gemini",
                tool_choice="auto"
            )

            # Extract validation call and optional skill calls.
            validation_call = None
            for tool_call in response.get("tool_calls", []):
                fn = tool_call.get("function", {})
                fn_name = fn.get("name")
                if fn_name == "validate_and_refine":
                    validation_call = tool_call
                elif fn_name in skill_registry.list_available():
                    planned_skill_calls.append(tool_call)

            if validation_call is not None:
                function_args = json.loads(validation_call["function"]["arguments"])
                type_state = function_args["type_state"]
                search_ops = function_args.get("search_ops", []) if type_state == "refine_query" else []

                # Backward compatibility: convert legacy search_ops into planned skill calls.
                if not planned_skill_calls and search_ops:
                    planned_skill_calls = _legacy_search_ops_to_planned_calls(search_ops)
            else:
                # Fallback to structured output when model returns no validation tool call.
                _, agentic_response_format = get_agentic_prompt_and_format(
                    question, answer, search_results, historical_search_ops, agentic_config
                )
                llm_output = await call_llm_with_fallback(
                    prompt_agentic,
                    model_name="gemini",
                    response_format=agentic_response_format
                )
                type_state = llm_output["type_state"]
                search_ops = llm_output.get("search_ops", []) if type_state == "refine_query" else []
                planned_skill_calls = _legacy_search_ops_to_planned_calls(search_ops)
        except Exception as e:
            # Fallback to structured output on error
            logger.warning(f"Function calling failed, falling back to structured output: {e}")
            _, agentic_response_format = get_agentic_prompt_and_format(question, answer, search_results, historical_search_ops, agentic_config)
            llm_output = await call_llm_with_fallback(
                prompt_agentic,
                model_name="gemini",
                response_format=agentic_response_format
            )
            type_state = llm_output["type_state"]
            search_ops = llm_output.get("search_ops", []) if type_state == "refine_query" else []
            planned_skill_calls = _legacy_search_ops_to_planned_calls(search_ops)
    else:
        type_state = "valid_answer"
        search_ops = []
        planned_skill_calls = []
        
    if type_state == "valid_answer":
        # Accept current answer: either limit reached or validation passed
        answer = state["answer"]
        planned_skill_calls = []
        search_ops = []
    else:  # type_state == "refine_query"
        # Refine query for another search iteration
        answer = ""  # Clear answer to trigger new search and generation
        
    
    return {
        **state,
        "search_ops": search_ops,
        "planned_skill_calls": planned_skill_calls,
        "answer": answer,
        "search_results": search_results,
    }

