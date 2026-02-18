# MCP (Model Context Protocol) Integration

## What is MCP

A protocol for connecting LLM applications to external data sources and tools.

## Use Cases in This Project

1. **Elasticsearch MCP Server**
   - Expose search operations as MCP tools
   - Better abstraction than direct Elasticsearch calls
   - Enables future multi-source search

## Implementation (Modern Best Practices)

```python
# lib/mcp/search_service.py
from pydantic import BaseModel
from lib.search.elastic_mix import ElasticMix
from typing import Literal

class SearchRequest(BaseModel):
    """Request for semantic document search."""
    query: str
    collection: str = "default"
    top_k: int = 10
    title_k: int = 3  # Internal parameter, can be hidden from LLM

class DocumentResult(BaseModel):
    """Search result document with metadata."""
    doc_id: str
    chunk_id: str
    text: str
    doc_title: str
    score: float
    index: int = 0  # Sequential index for display

class SearchService:
    """Service layer that maps collections to Elasticsearch indices."""
    def __init__(self, elastic_mix: ElasticMix):
        self.elastic_mix = elastic_mix
        # Map collection names to (title_index, chunk_index) tuples
        self.collection_map = {
            "default": ("miles_guo_titles", "miles_guo"),
            # Add more collections as needed:
            # "legal": ("legal_titles", "legal_chunks"),
            # "finance": ("finance_titles", "finance_chunks"),
        }
    
    async def search(self, request: SearchRequest) -> list[DocumentResult]:
        """Search documents in a collection using general search."""
        title_index, chunk_index = self.collection_map.get(
            request.collection, 
            self.collection_map["default"]
        )
        
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

# lib/mcp/elasticsearch_server.py
from mcp.server import Server
from lib.mcp.search_service import SearchService, SearchRequest, DocumentResult

class ElasticsearchMCPServer:
    def __init__(self, search_service: SearchService):
        self.server = Server("search-mcp")
        self.search_service = search_service
        self._register_tools()
    
    def _register_tools(self):
        @self.server.tool()
        async def search_documents(
            request: SearchRequest
        ) -> list[DocumentResult]:
            """Semantic document search across collections with reranking."""
            return await self.search_service.search(request)
```

## Key Design Principles

- **Strong typing**: Use Pydantic models for input/output schemas
- **Hide infrastructure**: LLM sees `collection`, not `title_index`/`chunk_index` names
- **Express capabilities**: Tool descriptions focus on "what" (semantic search) not "how" (two-step retrieval)
- **Stable interface**: Implementation details (search_ops, ES indices) are internal to SearchService
- **Match existing structure**: DocumentResult aligns with current search result format (doc_id, chunk_id, text, doc_title, score)

## Benefits

- Standardized tool interface
- Easy to add new data sources
- Better observability
- Can be used by other MCP clients
- LLM doesn't need to know infrastructure details

## Architecture

MCP server runs in parallel with existing internal architecture:

```
Current Internal Architecture (Unchanged):
rag_search_node → ElasticMix → Elasticsearch

New External Architecture (Parallel):
External Tools → MCP Client → MCP Server → SearchService → ElasticMix → Elasticsearch
```

## Integration with Existing Code

The MCP server is designed as an **external interface** that coexists with the existing internal system:

- **Previous Internal use**: Agentic workflow continues to use `ElasticMix` directly
- **New Internal and External use**: MCP server provides standardized interface for external tools, CLI, or other LLM applications
- **Shared backend**: Both paths use the same `ElasticMix` and `Elasticsearch` infrastructure

```python
# Internal workflow (unchanged)
# lib/agentic/nodes/rag_search_node.py
async def rag_search_node(state: AgentState, elastic_mix: ElasticMix) -> AgentState:
    # Existing code remains unchanged
    search_results = await elastic_mix.search_ops(
        search_ops, title_index, chunk_index, title_k=title_k, chunk_k=chunk_k
    )
    # ...

# External MCP interface (new)
# External tools can call MCP server to access search capabilities
# MCP server internally uses SearchService → ElasticMix
```

## Extending for Multiple Search Types

If you need to expose other search operations (search_doc, search_neighbour_chunks) as MCP tools:

```python
# lib/mcp/search_service.py (extended)
class DocumentSearchRequest(BaseModel):
    query: str
    doc_id: str
    collection: str = "default"
    top_k: int = 10

class NeighbourSearchRequest(BaseModel):
    doc_id: str
    chunk_id: str
    distance: int = 1
    collection: str = "default"

class SearchService:
    # ... existing code ...
    
    async def search_document(self, request: DocumentSearchRequest) -> list[DocumentResult]:
        """Search within a specific document."""
        title_index, chunk_index = self.collection_map.get(
            request.collection, self.collection_map["default"]
        )
        ops = [{
            "type": "search_doc",
            "query_list": [request.query],
            "doc_id": request.doc_id
        }]
        results = await self.elastic_mix.search_ops(
            ops, title_index, chunk_index, chunk_k=request.top_k
        )
        return [DocumentResult(**r) for r in results]
    
    async def search_neighbours(self, request: NeighbourSearchRequest) -> list[DocumentResult]:
        """Search neighbouring chunks."""
        # ... similar implementation ...
```

## Implementation Strategy

1. **Phase 1**: Create `SearchService` wrapper (no breaking changes)
   - Add `lib/mcp/search_service.py` that wraps `ElasticMix`
   - Keep existing `rag_search_node` and all internal code unchanged
   - Test SearchService with existing ElasticMix

2. **Phase 2**: Add MCP server (for external tools)
   - Create `lib/mcp/elasticsearch_server.py`
   - Expose search as MCP tools
   - Can be used by external MCP clients (other applications, CLI tools, etc.)

## Files to Create

- `lib/mcp/__init__.py`
- `lib/mcp/search_service.py` - Service layer wrapping ElasticMix
- `lib/mcp/elasticsearch_server.py` - MCP server implementation
- `lib/mcp/client.py` - MCP client wrapper (optional, for calling other MCP servers)

