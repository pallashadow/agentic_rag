from lib.agentic.config import AgentState
from lib.agentic.prompts import get_entry_prompt_and_format
from lib.language_detect import detect_query_lang
from lib.llm.litellm_api import call_llm_with_fallback, call_llm_with_tools
from lib.app_logger import get_logger
import json
import logging

logger = get_logger(__name__)


async def entry_llm_node(state: AgentState) -> AgentState:
    """
    First LLM node: Classify the input type and generate direct answer if needed.
    
    This node uses LLM with function calling to classify user queries into four categories:
    - "greeting": Casual conversation or greetings, returns friendly response directly
    - "insult": Inappropriate language, returns professional response directly
    - "unclear": Vague or ambiguous questions, returns clarification request directly
    - "need_rag": Clear substantive questions requiring information retrieval, triggers RAG flow
    
    For "need_rag" type, the node also generates initial expanded queries for RAG search.
    For other types, it generates direct answers and uses original question as expanded_queries.
    """
    question = state["question"]
    query_context = state.get("query_context", [])
    agentic_config = state.get("agentic_config", {})
    doc_lang = state.get("doc_lang", "zh")
    query_lang = detect_query_lang(question) or "zh"
    max_query_expand_k = agentic_config.get("max_query_expand_k", 1)
    # Enforce a safe lower bound because LLM tool constraints are best-effort.
    max_query_expand_k = max(1, int(max_query_expand_k))

    def _normalize_expanded_queries(raw_queries: object) -> list[str]:
        """Normalize and hard-cap expanded queries regardless of model compliance."""
        if not isinstance(raw_queries, list):
            return []
        cleaned = [
            q.strip()
            for q in raw_queries
            if isinstance(q, str) and q.strip()
        ]
        return cleaned[:max_query_expand_k]
    
    # Build prompt from YAML: body.template + optional cross_lang_section
    from lib.agentic.prompts.prompt_loader import load_prompt_template, render_prompt
    tmpl = load_prompt_template("entry_prompt.yaml", prompt_lang=doc_lang)
    cross_lang_section = ""
    if doc_lang != query_lang:
        cross_lang_block = (tmpl.get("cross_lang") or {}).get("template")
        if isinstance(cross_lang_block, str) and cross_lang_block.strip():
            cross_lang_section = cross_lang_block.format(doc_lang=doc_lang, query_lang=query_lang)
    prompt_entry = render_prompt(
        "entry_prompt.yaml",
        prompt_lang=doc_lang,
        question=question,
        query_context=query_context,
        cross_lang_section=cross_lang_section,
    )
    # Tool description for expanded_queries: from YAML, append cross-lang suffix when needed
    tool_descriptions = tmpl.get("tool_descriptions") or {}
    expand_desc = tool_descriptions.get("expanded_queries", "Expanded queries for RAG search (1-3 queries, 15 chars max each)")
    if doc_lang != query_lang:
        suffix = tool_descriptions.get("expanded_queries_cross_lang_suffix", "")
        if suffix:
            expand_desc += suffix.format(doc_lang=doc_lang)
        else:
            expand_desc += f". Must be in {doc_lang} only (documents language), not in user's language."
    # Define tools in OpenAI format (LiteLLM compatible)
    tools = [
        {
            "type": "function",
            "function": {
                "name": "classify_query",
                "description": "Classify user query and generate expanded queries for RAG search",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query_type": {
                            "type": "string",
                            "enum": ["greeting", "insult", "unclear", "need_rag"],
                            "description": "Classification of the user query"
                        },
                        "expanded_queries": {
                            "type": "array",
                            "items": {"type": "string"},
                            "minItems": 1,
                            "maxItems": max_query_expand_k,
                            "description": expand_desc,
                        },
                        "answer": {
                            "type": "string",
                            "description": "Direct answer for greeting/insult/unclear types, empty for need_rag"
                        }
                    },
                    "required": ["query_type", "expanded_queries", "answer"]
                }
            }
        }
    ]
    
    try:
        # Call LLM with function calling via LiteLLM
        response = await call_llm_with_tools(
            prompt_entry,
            tools=tools,
            model_name="gpt",
            tool_choice="required"  # Force function call
        )
        
        # Parse function call result
        if response["tool_calls"]:
            tool_call = response["tool_calls"][0]
            function_args = json.loads(tool_call["function"]["arguments"])
            
            query_type = function_args["query_type"]
            expanded_queries = _normalize_expanded_queries(function_args.get("expanded_queries", []))
            answer = function_args["answer"]
        else:
            # Fallback if no tool call (shouldn't happen with tool_choice="required")
            # Fall back to old structured output method
            _, entry_response_format = get_entry_prompt_and_format(
                question,
                query_context,
                agentic_config,
                prompt_lang=doc_lang,
            )
            llm_output = await call_llm_with_fallback(prompt_entry, model_name="gpt", response_format=entry_response_format)
            query_type = llm_output.get("query_type", "unclear")
            expanded_queries = _normalize_expanded_queries(llm_output.get("expanded_queries", []))
            answer = llm_output.get(
                "answer",
                "抱歉，我无法理解您的问题，请重新表述。"
                if doc_lang == "zh"
                else "Sorry, I could not understand your question. Please rephrase it.",
            )
    except Exception as e:
        # Fallback to old structured output method on error
        logger.warning(f"Function calling failed, falling back to structured output: {e}")
        _, entry_response_format = get_entry_prompt_and_format(
            question,
            query_context,
            agentic_config,
            prompt_lang=doc_lang,
        )
        llm_output = await call_llm_with_fallback(prompt_entry, model_name="gpt", response_format=entry_response_format)
        query_type = llm_output.get("query_type", "unclear")
        expanded_queries = _normalize_expanded_queries(llm_output.get("expanded_queries", []))
        answer = llm_output.get(
            "answer",
            "抱歉，我无法理解您的问题，请重新表述。"
            if doc_lang == "zh"
            else "Sorry, I could not understand your question. Please rephrase it.",
        )
    
    # Update state based on classification
    if query_type == "need_rag":
        # For RAG queries: empty answer triggers RAG flow.
        # Generate skill-native planned calls directly so rag_search_node can execute without legacy conversion.
        expanded_queries = [question] + expanded_queries
        search_config = state.get("search_config", {})
        chunk_k = search_config.get("chunk_k", 12)
        planned_skill_calls = [
            {
                "id": "entry_general_0",
                "function": {
                    "name": "general_search",
                    "arguments": json.dumps(
                        {"query_list": expanded_queries, "top_k": chunk_k},
                        ensure_ascii=False,
                    ),
                },
            }
        ]
        search_ops = [{"type": "search_general", "query_list": expanded_queries}]
        return {
            **state,
            "query_lang": query_lang,
            "query_type": query_type,
            "answer": "",
            "planned_skill_calls": planned_skill_calls,
            "search_ops": search_ops,
        }
    else:
        # For direct answer types: use LLM-generated answer
        return {
            **state,
            "query_lang": query_lang,
            "query_type": query_type,
            "answer": answer,
            "planned_skill_calls": [],
            "search_ops": None,
        }

