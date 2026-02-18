"""MCP server implementation for search operations."""

try:
    from mcp.server import Server
    MCP_AVAILABLE = True
except ImportError:
    MCP_AVAILABLE = False
    # Placeholder for when MCP library is not available
    class Server:
        def __init__(self, name: str):
            self.name = name
        def tool(self):
            def decorator(func):
                return func
            return decorator

from lib.mcp.search_service import (
    SearchService,
    SearchRequest,
    GeneralSearchRequest,
    DocumentSearchRequest,
    NeighbourSearchRequest,
    DocumentResult,
)
from lib.app_logger import get_logger

logger = get_logger(__name__)


class SearchMCPServer:
    """MCP server that exposes search operations as tools."""
    
    def __init__(self, search_service: SearchService):
        if not MCP_AVAILABLE:
            logger.warning(
                "MCP library not available. Install with: pip install mcp "
                "or poetry add mcp"
            )
        self.server = Server("search-mcp")
        self.search_service = search_service
        self._register_tools()
    
    def _register_tools(self):
        """Register MCP tools."""
        
        @self.server.tool()
        async def search_documents(
            request: SearchRequest
        ) -> list[DocumentResult]:
            """Semantic document search across collections with reranking."""
            return await self.search_service.search(request)
        
        @self.server.tool()
        async def general_search(
            request: GeneralSearchRequest
        ) -> list[DocumentResult]:
            """General document search with query list support."""
            return await self.search_service.general_search(request)
        
        @self.server.tool()
        async def document_search(
            request: DocumentSearchRequest
        ) -> list[DocumentResult]:
            """Search within a specific document."""
            return await self.search_service.document_search(request)
        
        @self.server.tool()
        async def neighbour_search(
            request: NeighbourSearchRequest
        ) -> list[DocumentResult]:
            """Search for neighbouring chunks within a document."""
            return await self.search_service.neighbour_search(request)
    
    async def search(self, request: SearchRequest) -> list[DocumentResult]:
        """
        Direct search method for internal use (bypasses MCP protocol).
        
        This method allows internal code to use SearchMCPServer as a unified interface
        without going through the MCP protocol layer.
        """
        return await self.search_service.search(request)
    
    async def general_search(self, request: GeneralSearchRequest) -> list[DocumentResult]:
        """
        Direct general search method for internal use (bypasses MCP protocol).
        """
        return await self.search_service.general_search(request)
    
    async def document_search(self, request: DocumentSearchRequest) -> list[DocumentResult]:
        """
        Direct document search method for internal use (bypasses MCP protocol).
        """
        return await self.search_service.document_search(request)
    
    async def neighbour_search(self, request: NeighbourSearchRequest) -> list[DocumentResult]:
        """
        Direct neighbour search method for internal use (bypasses MCP protocol).
        """
        return await self.search_service.neighbour_search(request)

