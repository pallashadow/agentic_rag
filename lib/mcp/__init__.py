"""MCP (Model Context Protocol) integration for external tool access."""

from lib.mcp.search_service import (
    SearchService,
    SearchRequest,
    GeneralSearchRequest,
    DocumentSearchRequest,
    NeighbourSearchRequest,
    NaiveSearchRequest,
    DocumentResult,
)
from lib.mcp.search_server import SearchMCPServer

__all__ = [
    "SearchService",
    "SearchRequest",
    "GeneralSearchRequest",
    "DocumentSearchRequest",
    "NeighbourSearchRequest",
    "NaiveSearchRequest",
    "DocumentResult",
    "SearchMCPServer",
]

