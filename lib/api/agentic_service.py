from typing import Any

from lib.agentic.config import get_agent_state_default
from lib.agentic.streaming import agentic_rag_stream
from lib.observability.langsmith import (
    create_trace_metadata,
    get_metadata_tags,
    langsmith_enabled,
    traced,
)


@traced(run_type="chain", name="agentic_rag_endpoint")
async def agentic_rag_core(
    agentic_base: Any,
    txt_query: str,
    chunk_index: str,
    query_context: list[str],
    title_k: int,
    chunk_k: int,
    query_expand_k: int,
    max_iter: int,
):
    state1 = get_agent_state_default(
        chunk_index,
        title_k,
        chunk_k,
        max_iter=max_iter,
        max_query_expand_k=query_expand_k,
    )
    state1["question"] = txt_query
    state1["query_context"] = query_context

    config = {}
    if langsmith_enabled():
        try:
            metadata = create_trace_metadata(
                endpoint="/agentic_rag",
                chunk_index=chunk_index,
                title_k=title_k,
                chunk_k=chunk_k,
                query_expand_k=query_expand_k,
                has_context=len(query_context) > 0,
                max_iter=max_iter,
            )
            tags = get_metadata_tags()
            tags.update({"api": "true", "non-stream": "true", "agentic": "true"})
            config = {"metadata": metadata, "tags": tags}
        except Exception:
            pass

    agentic_result = await agentic_base.ainvoke(state1, config=config if config else None)

    if langsmith_enabled():
        try:
            create_trace_metadata(
                search_count=agentic_result.get("search_count"),
                query_type=agentic_result.get("query_type"),
            )
        except Exception:
            pass

    return {
        "content": agentic_result["answer"],
        "search_results": agentic_result["search_results"],
        "historical_search_ops": agentic_result["historical_search_ops"],
        "query_type": agentic_result["query_type"],
        "search_count": agentic_result["search_count"],
        "chunk_index": agentic_result.get("chunk_index", chunk_index),
        "title_index": agentic_result.get("title_index", state1.get("title_index", "")),
        "query_lang": agentic_result.get("query_lang", state1.get("query_lang", "zh")),
        "doc_lang": agentic_result.get("doc_lang", state1.get("doc_lang", "zh")),
    }


@traced(run_type="chain", name="agentic_rag_stream_endpoint")
async def agentic_rag_stream_core(
    agentic_base: Any,
    txt_query: str,
    chunk_index: str,
    query_context: list[str],
    title_k: int,
    chunk_k: int,
    query_expand_k: int,
    max_iter: int,
):
    state1 = get_agent_state_default(
        chunk_index,
        title_k,
        chunk_k,
        max_iter=max_iter,
        max_query_expand_k=query_expand_k,
    )
    state1["question"] = txt_query
    state1["query_context"] = query_context[-4:] if query_context else []

    config = {}
    if langsmith_enabled():
        try:
            metadata = create_trace_metadata(
                endpoint="/agentic_rag_stream",
                chunk_index=chunk_index,
                title_k=title_k,
                chunk_k=chunk_k,
                query_expand_k=query_expand_k,
                has_context=len(query_context) > 0,
                max_iter=max_iter,
            )
            tags = get_metadata_tags()
            tags.update({"api": "true", "stream": "true", "agentic": "true"})
            config = {"metadata": metadata, "tags": tags}
        except Exception:
            pass

    return agentic_rag_stream(agentic_base, state1, config=config)

