# MCP (Model Context Protocol) Module

This module provides MCP integration for exposing search operations as external tools. It follows a layered architecture that separates business logic from protocol implementation.

## Architecture

The module follows a clean separation of concerns:

```
SearchMCPServer (Protocol Layer)
    ↓
SearchService (Business Logic Layer)
    ↓
ElasticMix (Search Implementation)
    ↓
Elasticsearch (Database)
```

### Layer Responsibilities

1. **SearchMCPServer** (`search_server.py`)
   - MCP protocol implementation
   - Exposes search operations as MCP tools
   - Protocol adapter layer (no business logic)

2. **SearchService** (`search_service.py`)
   - Business logic layer
   - Maps collections to Elasticsearch indices
   - Handles search operations and result formatting
   - Can be used independently (not tied to MCP)

3. **MCPClient** (`client.py`)
   - Client wrapper for calling other MCP servers
   - Currently a placeholder implementation

## Files

### `search_service.py`
Service layer that provides search functionality with collection abstraction.

**Classes:**
- `SearchRequest`: Request model for search operations
- `DocumentResult`: Search result model with metadata
- `SearchService`: Main service class that handles search logic

**Key Features:**
- Collection-to-index mapping (hides Elasticsearch index names from clients)
- Semantic document search with reranking
- Type-safe models using Pydantic

### `search_server.py`
MCP server implementation that exposes `SearchService` as MCP tools.

**Classes:**
- `SearchMCPServer`: MCP server that wraps `SearchService`

**Key Features:**
- Registers search operations as MCP tools
- Graceful handling when MCP library is not available
- Protocol abstraction layer

### `client.py`
MCP client wrapper for calling external MCP servers.

**Classes:**
- `MCPClient`: Client for calling MCP tools on remote servers

**Status:** Placeholder implementation (TODO: implement when MCP library is available)

### `__init__.py`
Module exports for convenient imports.

## Usage

### Basic Setup

```python
from lib.mcp import SearchService, SearchMCPServer
from lib.rag.rag_base import RAGBase

# Initialize with shared ElasticMix instance
rag_base = RAGBase()
search_service = SearchService(rag_base.elastic_mix)
mcp_server = SearchMCPServer(search_service)
```

### Using SearchService Directly

```python
from lib.mcp import SearchService, SearchRequest

# Create search request
request = SearchRequest(
    query="your search query",
    collection="default",
    top_k=10,
    title_k=3
)

# Execute search
results = await search_service.search(request)
```

### Adding New Collections

Edit `search_service.py` to add collection mappings:

```python
self.collection_map = {
    "default": ("miles_guo_titles", "miles_guo"),
    "legal": ("legal_titles", "legal_chunks"),
    "finance": ("finance_titles", "finance_chunks"),
}
```

## Design Principles

1. **Separation of Concerns**: Business logic (Service) is independent of protocol (Server)
2. **Reusability**: `SearchService` can be used without MCP
3. **Type Safety**: Pydantic models ensure type safety
4. **Abstraction**: Collection names hide Elasticsearch implementation details
5. **Extensibility**: Easy to add new search operations or collections

## Dependencies

- `mcp`: MCP library (optional, graceful fallback if not available)
- `pydantic`: For data models
- `lib.search.elastic_mix`: Search implementation
- `lib.app_logger`: Logging utilities

## Future Enhancements

- [ ] Implement `MCPClient` for calling external MCP servers
- [ ] Add more search operations (document-specific search, neighbor search)
- [ ] Support for multiple collections
- [ ] Enhanced error handling and validation

