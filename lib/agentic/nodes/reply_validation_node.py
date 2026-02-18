from lib.agentic.config import AgentState
from lib.agentic.prompts import get_agentic_prompt_and_format
from lib.llm.litellm_api import call_llm_with_fallback, call_llm_with_tools
from lib.agentic.prompts.prompt_loader import render_prompt
from lib.app_logger import get_logger
import json

logger = get_logger(__name__)


async def reply_validation_node(state: AgentState) -> AgentState:
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
        
        # Define tools for validation and refinement
        tools = [
            {
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
                                "description": "State indicating if answer is valid or needs refinement"
                            },
                            "search_ops": {
                                "type": "array",
                                "items": {
                                    "type": "object",
                                    "properties": {
                                        "type": {
                                            "type": "string",
                                            "enum": ["search_general", "search_doc", "search_neighbour_chunks"],
                                            "description": "Type of search operation"
                                        },
                                        "query_list": {
                                            "type": "array",
                                            "items": {"type": "string"},
                                            "description": "List of queries for search_general type"
                                        },
                                        "doc_id": {
                                            "type": "string",
                                            "description": "Document ID for search_doc or search_neighbour_chunks"
                                        },
                                        "chunk_id": {
                                            "type": "string",
                                            "description": "Chunk ID for search_neighbour_chunks"
                                        },
                                        "distance": {
                                            "type": "integer",
                                            "description": "Distance for search_neighbour_chunks"
                                        }
                                    }
                                },
                                "description": "Search operations to execute if type_state is refine_query"
                            },
                            "valid_search_indices": {
                                "type": "array",
                                "items": {"type": "integer"},
                                "description": "Indices of valid search results (for valid_answer state)"
                            }
                        },
                        "required": ["type_state", "search_ops"]
                    }
                }
            }
        ]
        
        try:
            # Call LLM with function calling
            response = await call_llm_with_tools(
                prompt_agentic,
                tools=tools,
                model_name="gemini",
                tool_choice="required"
            )
            
            # Parse function call result
            if response["tool_calls"]:
                tool_call = response["tool_calls"][0]
                function_args = json.loads(tool_call["function"]["arguments"])
                type_state = function_args["type_state"]
                search_ops = function_args.get("search_ops", []) if type_state == "refine_query" else []
            else:
                # Fallback to structured output
                _, agentic_response_format = get_agentic_prompt_and_format(question, answer, search_results, historical_search_ops, agentic_config)
                llm_output = await call_llm_with_fallback(
                    prompt_agentic,
                    model_name="gemini",
                    response_format=agentic_response_format
                )
                type_state = llm_output["type_state"]
                search_ops = llm_output.get("search_ops", []) if type_state == "refine_query" else []
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
    else:
        type_state = "valid_answer"
        search_ops = []
        
    if type_state == "valid_answer":
        # Accept current answer: either limit reached or validation passed
        answer = state["answer"]
    else:  # type_state == "refine_query"
        # Refine query for another search iteration
        answer = ""  # Clear answer to trigger new search and generation
        
    
    return {
        **state,
        "search_ops": search_ops,
        "answer": answer,
        "search_results": search_results,
    }

