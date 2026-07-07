import os
import json
import uvicorn
from typing import AsyncGenerator
from fastapi import FastAPI, HTTPException, Depends, Query
from fastapi.responses import StreamingResponse
from dotenv import load_dotenv
from lib.rag.rag_base import RAGBase
from lib.agentic.graph import AgenticGraph
from lib.index_mapping import get_index_meta
from lib.language_detect import detect_query_lang
from lib.app_logger import get_logger, setup_logging
from lib.security import setup_cors, require_auth, require_rate_limit, global_exception_handler
from lib.search.search_service import SearchService, SearchRequest
from lib.api.chatbot_service import chatbot_core, chatbot_stream_core
from lib.api.agentic_service import agentic_rag_core, agentic_rag_stream_core

app = FastAPI()
load_dotenv()
setup_logging()
logger = get_logger(__name__)
rag_base = RAGBase()
agentic_base = AgenticGraph().build_workflow().compile()

# Initialize the search service for the external search endpoint.
# Share the same ElasticMix instance with the internal workflow.
search_service = SearchService(rag_base.elastic_mix)
logger.info("SearchService initialized")


setup_cors(app)
app.add_exception_handler(Exception, global_exception_handler)

# SSE streaming helpers
SSE_HEADERS = {
    "Cache-Control": "no-cache",
    "Connection": "keep-alive",
    "X-Accel-Buffering": "no",  # Disable buffering in nginx
}

def format_sse_chunk(chunk: dict) -> str:
    """Format a dictionary chunk as Server-Sent Event."""
    data = json.dumps(chunk, ensure_ascii=False)
    return f"data: {data}\n\n"

async def wrap_stream_with_error_handling(
    stream_generator,
    error_context: str,
    extra_log_data: dict = None,
) -> AsyncGenerator[str, None]:
    """Wrap an async generator with error handling and SSE formatting."""
    try:
        async for chunk in stream_generator:
            yield format_sse_chunk(chunk)
    except Exception as e:
        logger.error(
            f"Error in {error_context}: %s",
            e,
            exc_info=True,
            extra=extra_log_data or {},
        )
        error_chunk = {"type": "error", "data": {"error": str(e)}}
        yield format_sse_chunk(error_chunk)

@app.get("/")
async def root():
    return {"message": "chatbot milesguo backend"}

@app.get("/version")
def version():
    return {"message": "v0.0.1"}

@app.get("/token")
def get_token():
    """Public endpoint to get the auth token for frontend auto-configuration."""
    from lib.security import _is_auth_enabled, _get_expected_token
    if _is_auth_enabled():
        return {"token": _get_expected_token()}
    return {"token": None}

@app.get("/search_naive")
async def search_naive(
    txt_query: str,
    chunk_index: str,
    k: int = 10,
    _: None = Depends(require_auth),
    __: None = Depends(require_rate_limit),
):
    try:
        search_results = await rag_base.search_naive(txt_query, chunk_index, chunk_k=k)
        return search_results
    except Exception as e:
        # Log all exceptions with full stack trace before converting to HTTPException
        logger.error("Error in search_naive: %s", e, exc_info=True, extra={"txt_query": txt_query, "k": k})
        # Surface actionable config errors (e.g., missing API keys) to the caller.
        raise HTTPException(status_code=500, detail=str(e)) from e

@app.get("/search")
async def search(
    txt_query: str,
    chunk_index: str,
    title_k: int = 3,
    chunk_k: int = 12,
    query_expand_k: int = 1,
    _: None = Depends(require_auth),
    __: None = Depends(require_rate_limit),
):
    try:
        doc_lang = get_index_meta(chunk_index)["doc_lang"]
        query_lang = detect_query_lang(txt_query) or doc_lang
        search_results, expanded_query = await rag_base.search(
            txt_query,
            chunk_index,
            title_k=title_k,
            chunk_k=chunk_k,
            query_expand_k=query_expand_k,
            doc_lang=doc_lang,
            query_lang=query_lang,
        )
        return search_results
    except Exception as e:
        # Log all exceptions with full stack trace before converting to HTTPException
        logger.error("Error in search: %s", e, exc_info=True, extra={"txt_query": txt_query, "title_k": title_k, "chunk_k": chunk_k, "query_expand_k": query_expand_k})
        # Surface actionable config errors (e.g., missing API keys) to the caller.
        raise HTTPException(status_code=500, detail=str(e)) from e

@app.get("/chatbot")
async def chatbot(
    txt_query: str,
    chunk_index: str,
    query_context: list[str] = Query(default=[]),
    title_k: int = 3,
    chunk_k: int = 12,
    query_expand_k: int = 1,
    _: None = Depends(require_auth),
    __: None = Depends(require_rate_limit),
):
    try:
        result = await chatbot_core(
            rag_base,
            txt_query,
            chunk_index,
            query_context,
            title_k,
            chunk_k,
            query_expand_k,
        )
        return result
    except Exception as e:
        # Log all exceptions with full stack trace before converting to HTTPException
        logger.error("Error in chatbot: %s", e, exc_info=True, extra={"txt_query": txt_query, "title_k": title_k, "chunk_k": chunk_k, "query_expand_k": query_expand_k})
        # Surface actionable config errors (e.g., missing API keys) to the caller.
        raise HTTPException(status_code=500, detail=str(e)) from e

@app.get("/chatbot_stream")
async def chatbot_stream(
    txt_query: str,
    chunk_index: str,
    query_context: list[str] = Query(default=[]),
    title_k: int = 3,
    chunk_k: int = 12,
    query_expand_k: int = 1,
    _: None = Depends(require_auth),
    __: None = Depends(require_rate_limit),
):
    """Stream chatbot response using Server-Sent Events (SSE)."""
    stream = await chatbot_stream_core(
        rag_base,
        txt_query,
        chunk_index,
        query_context,
        title_k,
        chunk_k,
        query_expand_k,
    )
    
    return StreamingResponse(
        wrap_stream_with_error_handling(
            stream,
            "chatbot_stream",
            {"txt_query": txt_query},
        ),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )

@app.get("/agentic_rag")
async def agentic_rag(
    txt_query: str,
    chunk_index: str,
    query_context: list[str] = Query(default=[]),
    title_k: int = 3,
    chunk_k: int = 12,
    query_expand_k: int = 1,
    max_iter: int = 2,
    _: None = Depends(require_auth),
    __: None = Depends(require_rate_limit),
):
    try:
        result = await agentic_rag_core(
            agentic_base,
            txt_query,
            chunk_index,
            query_context,
            title_k,
            chunk_k,
            query_expand_k,
            max_iter,
        )
        return result
    except Exception as e:
        logger.error("Error in agentic_rag: %s", e, exc_info=True, extra={
            "txt_query": txt_query,
            "title_k": title_k,
            "chunk_k": chunk_k,
            "query_expand_k": query_expand_k,
            "max_iter": max_iter,
        })
        raise HTTPException(status_code=500, detail=str(e)) from e

@app.get("/agentic_rag_stream")
async def agentic_rag_stream_endpoint(
    txt_query: str,
    chunk_index: str,
    query_context: list[str] = Query(default=[]),
    title_k: int = 3,
    chunk_k: int = 12,
    query_expand_k: int = 1,
    max_iter: int = 2,
    _: None = Depends(require_auth),
    __: None = Depends(require_rate_limit),
):
    """Stream agentic RAG response using Server-Sent Events (SSE)."""
    stream = await agentic_rag_stream_core(
        agentic_base,
        txt_query,
        chunk_index,
        query_context,
        title_k,
        chunk_k,
        query_expand_k,
        max_iter,
    )
    
    return StreamingResponse(
        wrap_stream_with_error_handling(
            stream,
            "agentic_rag_stream",
            {"txt_query": txt_query},
        ),
        media_type="text/event-stream",
        headers=SSE_HEADERS,
    )

@app.get("/search")
async def search_documents(
    query: str,
    chunk_index: str = "miles_guo",
    top_k: int = 10,
    title_k: int = 3,
    _: None = Depends(require_auth),
    __: None = Depends(require_rate_limit),
):
    """
    External search endpoint - standardized interface for external tools.

    Uses SearchService, which provides a clean abstraction over Elasticsearch
    indices. It coexists with the internal workflow that uses ElasticMix
    directly. The title_index is automatically derived from chunk_index.
    """
    try:
        request = SearchRequest(
            query=query,
            chunk_index=chunk_index,
            top_k=top_k,
            title_k=title_k,
        )
        results = await search_service.search(request)
        # Convert Pydantic models to dict for JSON serialization
        return {
            "results": [result.model_dump() for result in results],
            "count": len(results),
        }
    except Exception as e:
        logger.error("Error in search_documents: %s", e, exc_info=True, extra={"query": query, "chunk_index": chunk_index})
        raise HTTPException(status_code=500, detail=str(e)) from e


# Start server when run directly or in Cloud Functions 2nd gen
# Cloud Functions 2nd gen runs main.py as script, so __name__ == "__main__" will be True
# Check K_SERVICE (Cloud Run sets this) as additional indicator for Cloud Functions 2nd gen
if __name__ == "__main__" or os.environ.get("K_SERVICE"):
    port = int(os.environ.get("PORT", 8080))
    uvicorn.run(app, host="0.0.0.0", port=port)
