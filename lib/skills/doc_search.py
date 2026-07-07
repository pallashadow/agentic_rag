"""
Document-specific search skill for searching within a known document.
"""
from pydantic import BaseModel, Field
from lib.search.search_service import SearchService, DocumentSearchRequest
from lib.skills.base import BaseSkill, SkillInput, SkillOutput
from lib.skills.general_search import DocumentResult
from lib.agentic.config import AgentState


class DocumentSearchInput(SkillInput):
    """Input schema for document-specific search."""
    query: str = Field(..., description="Search query")
    doc_id: str = Field(..., description="Document ID to search within")
    top_k: int = Field(default=5, ge=1, le=20)


class DocumentSearchOutput(SkillOutput):
    """Output schema for document search."""
    results: list[DocumentResult]
    doc_id: str
    total_found: int


class DocumentSearchSkill(BaseSkill):
    """Search within a specific document."""
    
    name = "document_search"
    description = (
        "Search for content within a specific document. "
        "Useful when you know the document ID and want to find specific information within it. "
        "More precise than general search but requires prior knowledge of document structure."
    )
    input_model = DocumentSearchInput
    output_model = DocumentSearchOutput
    
    def __init__(self, search_service: SearchService):
        self.search_service = search_service

    async def execute(
        self,
        input_data: DocumentSearchInput,
        state: AgentState | None = None,
    ) -> DocumentSearchOutput:
        """Execute document-specific search."""
        if state is None:
            raise ValueError("state is required to inherit chunk_index")

        search_config = state.get("search_config", {})
        chunk_index = search_config.get("chunk_index", "miles_guo")

        request = DocumentSearchRequest(
            query=input_data.query,
            doc_id=input_data.doc_id,
            chunk_index=chunk_index,
            top_k=input_data.top_k
        )

        service_results = await self.search_service.document_search(request)

        # Convert service DocumentResult to skill DocumentResult
        results = [
            DocumentResult(
                doc_id=r.doc_id,
                chunk_id=r.chunk_id,
                text=r.text,
                doc_title=r.doc_title,
                score=r.score,
                index=r.index
            )
            for r in service_results
        ]

        return DocumentSearchOutput(
            results=results,
            doc_id=input_data.doc_id,
            total_found=len(results)
        )

