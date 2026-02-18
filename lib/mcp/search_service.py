"""Service layer for Elasticsearch search operations."""

from pydantic import BaseModel, Field
from lib.search.elastic_mix import ElasticMix
from lib.app_logger import get_logger

logger = get_logger(__name__)


class SearchRequest(BaseModel):
    """Request for semantic document search."""
    query: str
    chunk_index: str
    top_k: int = 10
    title_k: int = 3  # Internal parameter, can be hidden from LLM


class GeneralSearchRequest(BaseModel):
    """Request for general search with query list support."""
    query_list: list[str] = Field(..., min_length=1, max_length=5)
    chunk_index: str
    top_k: int = 5
    title_k: int = 3  # Internal parameter, can be hidden from LLM


class DocumentSearchRequest(BaseModel):
    """Request for document-specific search."""
    query: str
    doc_id: str
    chunk_index: str
    top_k: int = 5


class NeighbourSearchRequest(BaseModel):
    """Request for neighbour chunk search."""
    doc_id: str
    chunk_id: str
    chunk_index: str
    distance: int = Field(default=1, ge=1, le=5)


class NaiveSearchRequest(BaseModel):
    """Request for naive chunk search (direct chunk search without title filtering)."""
    query: str
    chunk_index: str
    top_k: int = 10
    doc_ids: list[str] = None


class DocumentResult(BaseModel):
    """Search result document with metadata."""
    doc_id: str
    chunk_id: str
    text: str
    doc_title: str
    score: float
    index: int = 0  # Sequential index for display


class SearchService:
    """Service layer for Elasticsearch search operations."""
    
    def __init__(self, elastic_mix: ElasticMix):
        self.elastic_mix = elastic_mix
    
    async def search(self, request: SearchRequest) -> list[DocumentResult]:
        """Search documents using general search."""
        # Derive title_index from chunk_index in MCP layer
        title_index = f"{request.chunk_index}_titles"
        chunk_index = request.chunk_index
        
        # Use search_ops with search_general operation
        ops = [{
            "type": "search_general",
            "query_list": [request.query]
        }]
        
        results = await self.elastic_mix.search_ops(
            ops,
            title_index=title_index,
            chunk_index=chunk_index,
            title_k=request.title_k,
            chunk_k=request.top_k
        )
        
        # Convert dict results to DocumentResult models
        return [
            DocumentResult(
                doc_id=r.get("doc_id", ""),
                chunk_id=r.get("chunk_id", ""),
                text=r.get("text", ""),
                doc_title=r.get("doc_title", ""),
                score=r.get("score", 0.0),
                index=r.get("index", 0)
            )
            for r in results
        ]
    
    async def general_search(self, request: GeneralSearchRequest) -> list[DocumentResult]:
        """General search with query list support."""
        # Derive title_index from chunk_index in MCP layer
        title_index = f"{request.chunk_index}_titles"
        chunk_index = request.chunk_index
        
        # Use search_ops with search_general operation
        ops = [{
            "type": "search_general",
            "query_list": request.query_list
        }]
        
        results = await self.elastic_mix.search_ops(
            ops,
            title_index=title_index,
            chunk_index=chunk_index,
            title_k=request.title_k,
            chunk_k=request.top_k
        )
        
        # Convert dict results to DocumentResult models
        return [
            DocumentResult(
                doc_id=r.get("doc_id", ""),
                chunk_id=r.get("chunk_id", ""),
                text=r.get("text", ""),
                doc_title=r.get("doc_title", ""),
                score=r.get("score", 0.0),
                index=r.get("index", 0)
            )
            for r in results
        ]
    
    async def document_search(self, request: DocumentSearchRequest) -> list[DocumentResult]:
        """Search within a specific document."""
        chunk_index = request.chunk_index
        
        # Use search_ops with search_doc operation
        ops = [{
            "type": "search_doc",
            "query_list": [request.query],
            "doc_id": request.doc_id
        }]
        
        results = await self.elastic_mix.search_ops(
            ops,
            title_index="",  # Not used for document search
            chunk_index=chunk_index,
            title_k=0,
            chunk_k=request.top_k
        )
        
        # Convert dict results to DocumentResult models
        return [
            DocumentResult(
                doc_id=r.get("doc_id", ""),
                chunk_id=r.get("chunk_id", ""),
                text=r.get("text", ""),
                doc_title=r.get("doc_title", ""),
                score=r.get("score", 0.0),
                index=r.get("index", 0)
            )
            for r in results
        ]
    
    async def neighbour_search(self, request: NeighbourSearchRequest) -> list[DocumentResult]:
        """Search for neighbouring chunks."""
        chunk_index = request.chunk_index
        
        # Use search_ops with search_neighbour_chunks operation
        ops = [{
            "type": "search_neighbour_chunks",
            "doc_id": request.doc_id,
            "chunk_id": request.chunk_id,
            "distance": request.distance
        }]
        
        results = await self.elastic_mix.search_ops(
            ops,
            title_index="",  # Not used for neighbour search
            chunk_index=chunk_index,
            title_k=0,
            chunk_k=0  # Not used for neighbour search
        )
        
        # Convert dict results to DocumentResult models
        return [
            DocumentResult(
                doc_id=r.get("doc_id", ""),
                chunk_id=r.get("chunk_id", ""),
                text=r.get("text", ""),
                doc_title=r.get("doc_title", ""),
                score=r.get("score", 0.0),
                index=r.get("index", 0)
            )
            for r in results
        ]
    
    async def naive_search(self, request: NaiveSearchRequest) -> list[DocumentResult]:
        """Naive search - direct chunk search without title filtering."""
        # Use elastic_mix.search_naive directly
        results = await self.elastic_mix.search_naive(
            request.query,
            request.chunk_index,
            chunk_k=request.top_k,
            doc_ids=request.doc_ids
        )
        
        # Convert dict results to DocumentResult models
        return [
            DocumentResult(
                doc_id=r.get("doc_id", ""),
                chunk_id=r.get("chunk_id", ""),
                text=r.get("text", ""),
                doc_title=r.get("doc_title", ""),
                score=r.get("score", 0.0),
                index=i
            )
            for i, r in enumerate(results, start=1)
        ]

