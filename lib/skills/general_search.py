"""
General document search skill with query expansion and two-step retrieval.
"""
from pydantic import BaseModel, Field
from lib.search.search_service import SearchService, GeneralSearchRequest
from lib.skills.base import BaseSkill, SkillInput, SkillOutput
from lib.agentic.config import AgentState


class GeneralSearchInput(SkillInput):
    """Input schema for general document search."""
    query_list: list[str] = Field(
        ...,
        description="List of expanded queries for semantic search (1-3 queries recommended)",
        min_length=1,
        max_length=5
    )
    top_k: int = Field(
        default=5,
        description="Number of top results to return",
        ge=1,
        le=20
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
    
    def __init__(self, search_service: SearchService):
        self.search_service = search_service

    async def execute(
        self,
        input_data: GeneralSearchInput,
        state: AgentState | None = None,
    ) -> GeneralSearchOutput:
        """Execute general search with validated input."""
        if state is None:
            raise ValueError("state is required to inherit chunk_index and title_k")

        search_config = state.get("search_config", {})
        chunk_index = search_config.get("chunk_index", "miles_guo")
        title_k = search_config.get("title_k", 3)

        # title_index is derived from chunk_index inside the search service
        request = GeneralSearchRequest(
            query_list=input_data.query_list,
            chunk_index=chunk_index,
            top_k=input_data.top_k,
            title_k=title_k
        )

        service_results = await self.search_service.general_search(request)

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

        return GeneralSearchOutput(
            results=results,
            total_found=len(results),
            queries_used=input_data.query_list
        )

