from lib.agentic.config import AgentState
from lib.search.elastic_mix import ElasticMix
from lib.mcp import SearchService, SearchRequest, DocumentSearchRequest, NeighbourSearchRequest
from lib.app_logger import get_logger

logger = get_logger(__name__)


async def rag_search_node(state: AgentState, elastic_mix: ElasticMix) -> AgentState:
    """
    Second node (non-LLM): Perform RAG search with expanded queries.
    
    This node executes the actual search operation using the expanded queries generated
    in previous nodes. It increments the search_count to track how many search iterations
    have been performed, which is used to prevent infinite loops in the RAG flow.
    
    The search results are stored in state for use by subsequent LLM nodes that generate
    answers or validate the quality of retrieved information.
    """
    search_config = state["search_config"]
    search_ops = state["search_ops"]
    historical_search_ops = state["historical_search_ops"]
    if search_ops is None:
        search_ops = [{"type": "search_general", "query_list": [state["question"]]}]
    historical_search_ops = historical_search_ops + search_ops
    chunk_index = search_config["chunk_index"]
    title_k = search_config["title_k"]
    chunk_k = search_config["chunk_k"]
    
    # Use MCP SearchService instead of direct elastic_mix calls
    # SearchMCPServer is only for external MCP clients, internal code uses SearchService directly
    search_service = SearchService(elastic_mix)
    
    # Process each search operation and combine results
    all_results = []
    for search_op in search_ops:
        search_type = search_op.get("type")
        
        if search_type == "search_general":
            query_list = search_op.get("query_list", [])
            for query in query_list:
                # Create SearchRequest with only chunk_index - title_index conversion happens in MCP layer
                request = SearchRequest(
                    query=query,
                    chunk_index=chunk_index,
                    top_k=chunk_k,
                    title_k=title_k
                )
                doc_results = await search_service.search(request)
                # Convert DocumentResult back to dict format for compatibility
                all_results.extend([
                    {
                        "doc_id": r.doc_id,
                        "chunk_id": r.chunk_id,
                        "text": r.text,
                        "doc_title": r.doc_title,
                        "score": r.score,
                        "index": r.index
                    }
                    for r in doc_results
                ])
        
        elif search_type == "search_doc":
            query_list = search_op.get("query_list", [])
            doc_id = search_op.get("doc_id")
            if not doc_id:
                logger.warning("search_doc operation missing doc_id, skipping")
                continue
            if not query_list:
                logger.warning("search_doc operation missing query_list, skipping")
                continue
            
            # Process each query in the query_list for document search
            for query in query_list:
                request = DocumentSearchRequest(
                    query=query,
                    doc_id=doc_id,
                    chunk_index=chunk_index,
                    top_k=chunk_k
                )
                doc_results = await search_service.document_search(request)
                # Convert DocumentResult back to dict format for compatibility
                all_results.extend([
                    {
                        "doc_id": r.doc_id,
                        "chunk_id": r.chunk_id,
                        "text": r.text,
                        "doc_title": r.doc_title,
                        "score": r.score,
                        "index": r.index
                    }
                    for r in doc_results
                ])
        
        elif search_type == "search_neighbour_chunks":
            doc_id = search_op.get("doc_id")
            chunk_id = search_op.get("chunk_id")
            distance = search_op.get("distance", 1)
            
            if not doc_id or not chunk_id:
                logger.warning("search_neighbour_chunks operation missing doc_id or chunk_id, skipping")
                continue
            
            request = NeighbourSearchRequest(
                doc_id=doc_id,
                chunk_id=chunk_id,
                chunk_index=chunk_index,
                distance=distance
            )
            doc_results = await search_service.neighbour_search(request)
            # Convert DocumentResult back to dict format for compatibility
            all_results.extend([
                {
                    "doc_id": r.doc_id,
                    "chunk_id": r.chunk_id,
                    "text": r.text,
                    "doc_title": r.doc_title,
                    "score": r.score,
                    "index": r.index
                }
                for r in doc_results
            ])
        
        else:
            logger.warning(f"Unknown search operation type: {search_type}, skipping")
    
    search_results = all_results
    
    # Original direct call code (commented out):
    # search_results = await elastic_mix.search_ops(
    #     search_ops, 
    #     title_index, 
    #     chunk_index, 
    #     title_k=title_k, 
    #     chunk_k=chunk_k, 
    # )
    
    # Increment search count to track RAG search iterations
    search_count = state.get("search_count", 0) + 1
    
    return {
        **state,
        "search_results": search_results,
        "search_count": search_count,
        "historical_search_ops": historical_search_ops,
    }

