"""
Neighbour chunk search skill for finding adjacent chunks within a document.
"""
from pydantic import BaseModel, Field
from lib.mcp.search_server import SearchMCPServer
from lib.mcp.search_service import NeighbourSearchRequest
from lib.skills.base import BaseSkill, SkillInput, SkillOutput
from lib.skills.general_search import DocumentResult


class NeighbourSearchInput(SkillInput):
    """Input schema for neighbour chunk search."""
    doc_id: str = Field(..., description="Document ID containing the chunk")
    chunk_id: str = Field(..., description="Chunk ID to find neighbours for")
    chunk_index: str = Field(..., description="Elasticsearch index name for document chunks")
    distance: int = Field(
        default=1,
        description="Distance from the chunk to search (number of chunks away)",
        ge=1,
        le=5
    )


class NeighbourSearchOutput(SkillOutput):
    """Output schema for neighbour search."""
    results: list[DocumentResult]
    doc_id: str
    chunk_id: str
    distance: int
    total_found: int


class NeighbourSearchSkill(BaseSkill):
    """Search for neighbouring chunks within a document."""
    
    name = "neighbour_search"
    description = (
        "Find neighbouring chunks around a specific chunk within a document. "
        "Useful for retrieving context around a known chunk, such as when you want "
        "to see surrounding paragraphs or sections. The distance parameter controls "
        "how many chunks away to search."
    )
    input_model = NeighbourSearchInput
    output_model = NeighbourSearchOutput
    
    def __init__(self, mcp_server: SearchMCPServer):
        self.mcp_server = mcp_server
    
    async def execute(self, input_data: NeighbourSearchInput) -> NeighbourSearchOutput:
        """Execute neighbour chunk search via MCP."""
        # Create MCP request with all parameters
        mcp_request = NeighbourSearchRequest(
            doc_id=input_data.doc_id,
            chunk_id=input_data.chunk_id,
            chunk_index=input_data.chunk_index,
            distance=input_data.distance
        )
        
        # Call MCP server
        mcp_results = await self.mcp_server.neighbour_search(mcp_request)
        
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
        
        return NeighbourSearchOutput(
            results=results,
            doc_id=input_data.doc_id,
            chunk_id=input_data.chunk_id,
            distance=input_data.distance,
            total_found=len(results)
        )

