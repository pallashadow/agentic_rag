from lib.agentic.config import AgentState
from lib.skills import create_default_skill_registry
from lib.agentic.nodes import (
    entry_llm_node as _entry_llm_node,
    rag_search_node as _rag_search_node,
    rag_reply_node as _rag_reply_node,
    reply_validation_node as _reply_validation_node,
)


class Node:
    """
    Node class containing all workflow node functions.
    Each method represents a node in the agentic RAG workflow.
    """
    
    def __init__(self):
        # Build skill registry via skills-layer factory to keep MCP hidden from nodes.
        self.skill_registry = create_default_skill_registry()

    async def entry_llm_node(self, state: AgentState) -> AgentState:
        """Wrapper for entry_llm_node from lib.agentic.nodes."""
        return await _entry_llm_node(state)

    async def rag_search_node(self, state: AgentState) -> AgentState:
        """Wrapper for rag_search_node from lib.agentic.nodes."""
        return await _rag_search_node(state, self.skill_registry)
        
    async def rag_reply_node(self, state: AgentState) -> AgentState:
        """Wrapper for rag_reply_node from lib.agentic.nodes."""
        return await _rag_reply_node(state)

    async def reply_validation_node(self, state: AgentState) -> AgentState:
        """Wrapper for reply_validation_node from lib.agentic.nodes."""
        return await _reply_validation_node(state, self.skill_registry)

