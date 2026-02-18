from typing import TypedDict, List, Literal
from langgraph.graph import END
from lib.agentic.config import AgentState


class Edge:
    """
    Edge class containing all routing functions for conditional edges in the workflow.
    Each method determines the next node based on the current state.
    """
    
    def route_after_entry(self, state: AgentState) -> str:
        """
        Route after entry_llm_node:
        - If greeting/insult/unclear: answer already generated, go to END
        - If need_rag: continue to RAG flow (rag_search_node)
        """
        query_type = state.get("query_type", "unclear")
        
        if query_type == "need_rag":
            return "rag_search"
        else:
            # greeting, insult, or unclear - answer already generated in first node
            return END

    def route_after_validation(self, state: AgentState) -> str:
        """
        Route after reply_validation_node:
        - If valid_answer or exceeded_limit: go to END (answer is ready)
        - If refine_query: loop back to rag_search_node for another iteration
        """
        agentic_config = state.get("agentic_config", {})
        max_iter = agentic_config.get("max_iter", 3)
        search_count = state.get("search_count", 0)
        exceeded_limit = search_count >= max_iter
        
        # Check if we have planned tool calls to execute.
        planned_skill_calls = state.get("planned_skill_calls")

        # Legacy search_ops fallback is intentionally disabled.
        has_legacy_ops = False
        has_skill_calls = planned_skill_calls is not None and len(planned_skill_calls) > 0
        if exceeded_limit or (not has_legacy_ops and not has_skill_calls):
            # No more search operations to execute, answer is ready
            return END
        else:
            # Need to refine, loop back to search
            return "rag_search"

