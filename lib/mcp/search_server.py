"""MCP server implementation for search operations.

SearchMCPServer acts as a unified interface over SearchService. Skills call its
methods (general_search, document_search, neighbour_search, search) directly.
"""

from lib.mcp.search_service import (
    SearchService,
    SearchRequest,
    GeneralSearchRequest,
    DocumentSearchRequest,
    NeighbourSearchRequest,
    DocumentResult,
)


class SearchMCPServer:
    """Unified search interface exposing search operations to skills."""

    def __init__(self, search_service: SearchService):
        self.search_service = search_service
    
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

