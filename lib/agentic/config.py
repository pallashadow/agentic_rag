from typing import TypedDict, List, Any

from lib.index_mapping import get_index_meta

class SearchConfig(TypedDict):
    title_index: str
    chunk_index: str
    title_k: int
    chunk_k: int
    
class AgenticConfig(TypedDict):
    max_iter: int
    max_query_expand_k: int

# 1. 定义状态结构
class AgentState(TypedDict, total=False):
    question: str # init user query
    query_context: List[str] # query context for RAG search
    answer: str # final answer
    chunk_index: str
    title_index: str
    query_lang: str
    doc_lang: str
    query_type: str  # "greeting", "insult", "unclear", "need_rag"
    historical_search_ops: List[dict[str, Any]] # all search ops / skill calls that have been used
    search_ops: List[dict[str, Any]] # legacy search ops for backward compatibility
    planned_skill_calls: List[dict[str, Any]] # skill calls planned by reasoning node
    skill_errors: List[dict[str, Any]] # non-fatal skill execution errors
    search_results: List[dict] # search_results for RAG answer
    search_count: int # turns of RAG search
    search_config: SearchConfig # search config
    agentic_config: AgenticConfig # agentic config
    enable_streaming: bool # enable streaming output in rag_reply_node
    
def get_agent_state_default(
    chunk_index: str = "miles_guo",
    title_k: int = 3,
    chunk_k: int = 12,
    max_iter: int = 2,
    max_query_expand_k: int = 2,
    ):
    """
    Get default AgentState dictionary with all fields initialized.
    TypedDict cannot be instantiated like a class, so we return a plain dict.
    query_lang is detected in entry_llm_node and written to state.
    """
    index_meta = get_index_meta(chunk_index)
    title_index = index_meta["title_index"]
    doc_lang = index_meta["doc_lang"]
    
    return {
        "question": "",
        "query_context": [],
        "answer": "",
        "chunk_index": chunk_index,
        "title_index": title_index,
        "query_lang": "zh",
        "doc_lang": doc_lang,
        "query_type": "",
        "historical_search_ops": [],
        "search_ops": [],
        "planned_skill_calls": [],
        "skill_errors": [],
        "search_results": [],
        "search_count": 0,
        "search_config": {
            "title_index": title_index,
            "chunk_index": chunk_index,
            "title_k": title_k,
            "chunk_k": chunk_k,
        }, 
        "agentic_config": {
            "max_query_expand_k": max_query_expand_k,
            "max_iter": max_iter,
        }
    }
