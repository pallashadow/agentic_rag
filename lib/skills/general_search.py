"""
General document search skill with query expansion and two-step retrieval.
"""
from pydantic import BaseModel, Field
from lib.mcp.search_server import SearchMCPServer
from lib.mcp.search_service import GeneralSearchRequest
from lib.skills.base import BaseSkill, SkillInput, SkillOutput
from typing import Literal


class GeneralSearchInput(SkillInput):
    """Input schema for general document search."""
    query_list: list[str] = Field(
        ...,
        description="List of expanded queries for semantic search (1-3 queries recommended)",
        min_length=1,
        max_length=5
    )
    chunk_index: str = Field(
        ...,
        description="Elasticsearch index name for document chunks (title index is derived automatically)"
    )
    top_k: int = Field(
        default=5,
        description="Number of top results to return",
        ge=1,
        le=20
    )
    title_k: int = Field(
        default=3,
        description="Number of title results to retrieve (internal parameter)",
        ge=1,
        le=10
    )


class DocumentResult(BaseModel):
    """Single search result document."""
    doc_id: str
    chunk_id: str
    text: str
    doc_title: str
    score: float
    index: int = 0


class GeneralSearchOutput(SkillOutput):
    """Output schema for general search results."""
    results: list[DocumentResult]
    total_found: int
    queries_used: list[str]


class GeneralSearchSkill(BaseSkill):
    """General document search using query expansion and two-step retrieval."""
    
    name = "general_search"
    description = (
        "Search documents using semantic search with query expansion. "
        "Uses a two-step retrieval strategy: first finds relevant document titles, "
        "then searches within those documents for precise chunks. "
        "Best for broad queries that need comprehensive coverage."
    )
    input_model = GeneralSearchInput
    output_model = GeneralSearchOutput
    
    def __init__(self, mcp_server: SearchMCPServer):
        self.mcp_server = mcp_server
    
    async def execute(self, input_data: GeneralSearchInput) -> GeneralSearchOutput:
        """Execute general search with validated input via MCP."""
        # Create MCP request - title_index is derived from chunk_index in MCP layer
        mcp_request = GeneralSearchRequest(
            query_list=input_data.query_list,
            chunk_index=input_data.chunk_index,
            top_k=input_data.top_k,
            title_k=input_data.title_k
        )
        
        # Call MCP server
        mcp_results = await self.mcp_server.general_search(mcp_request)
        
        # Convert MCP DocumentResult to skill DocumentResult
        results = [
            DocumentResult(
                doc_id=r.doc_id,
                chunk_id=r.chunk_id,
                text=r.text,
                doc_title=r.doc_title,
                score=r.score,
                index=r.index
            )
            for r in mcp_results
        ]
        
        return GeneralSearchOutput(
            results=results,
            total_found=len(results),
            queries_used=input_data.query_list
        )

