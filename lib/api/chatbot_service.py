from typing import Any

from lib.index_mapping import get_index_meta
from lib.language_detect import detect_query_lang
from lib.observability.langsmith import traced


@traced(run_type="chain", name="chatbot_endpoint")
async def chatbot_core(
    rag_base: Any,
    txt_query: str,
    chunk_index: str,
    query_context: list[str],
    title_k: int,
    chunk_k: int,
    query_expand_k: int,
):
    # Keep only the most recent context turns to control token usage.
    query_context_limited = query_context[-4:] if query_context else []
    query_lang = detect_query_lang(txt_query)
    doc_lang = get_index_meta(chunk_index)["doc_lang"]
    return await rag_base.chat(
        txt_query,
        chunk_index,
        query_context=query_context_limited,
        title_k=title_k,
        chunk_k=chunk_k,
        query_expand_k=query_expand_k,
        query_lang=query_lang,
        doc_lang=doc_lang,
    )


@traced(run_type="chain", name="chatbot_stream_endpoint")
async def chatbot_stream_core(
    rag_base: Any,
    txt_query: str,
    chunk_index: str,
    query_context: list[str],
    title_k: int,
    chunk_k: int,
    query_expand_k: int,
):
    query_context_limited = query_context[-4:] if query_context else []
    query_lang = detect_query_lang(txt_query)
    doc_lang = get_index_meta(chunk_index)["doc_lang"]
    return rag_base.chat_stream(
        txt_query,
        chunk_index,
        query_context=query_context_limited,
        title_k=title_k,
        chunk_k=chunk_k,
        query_expand_k=query_expand_k,
        query_lang=query_lang,
        doc_lang=doc_lang,
    )

