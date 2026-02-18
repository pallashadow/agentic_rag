# Skill/Plugin System (Agent-Native Cognitive Capability Layer)

## Current Limitation

Search operations are hardcoded in `elastic_mix.py`. Adding new search strategies requires code changes.

## Modern Solution

Agent-native skill system with cognitive capability abstraction

## Key Distinction

This is not just a "plugin architecture" (Strategy Pattern), but a **cognitive capability layer** where skills are:
- **Agent-visible capabilities** that LLMs can understand and select
- **Tool-semantic units** with explicit schemas for LLM reasoning
- **Composable reasoning units** that can be chained by planners
- **MCP-exportable tools** for standardized interfaces

## Implementation

```python
# lib/skills/base.py
from abc import ABC, abstractmethod
from pydantic import BaseModel
from typing import Type, Any
import json

class SkillInput(BaseModel):
    """Base class for skill input schemas."""
    pass

class SkillOutput(BaseModel):
    """Base class for skill output schemas."""
    pass

class BaseSkill(ABC):
    """Base class for agent-native skills with tool semantics."""
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Unique skill identifier."""
        ...
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Human-readable description for LLM understanding."""
        ...
    
    @property
    @abstractmethod
    def input_model(self) -> Type[SkillInput]:
        """Pydantic model defining input schema."""
        ...
    
    @property
    @abstractmethod
    def output_model(self) -> Type[SkillOutput]:
        """Pydantic model defining output schema."""
        ...
    
    def to_tool_schema(self) -> dict:
        """Export skill as OpenAI-compatible tool schema for LLM calling."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.input_model.model_json_schema()
            }
        }
    
    def to_mcp_tool_spec(self) -> dict:
        """Export skill as MCP tool specification."""
        return {
            "name": self.name,
            "description": self.description,
            "inputSchema": self.input_model.model_json_schema()
        }
    
    @abstractmethod
    async def execute(self, input_data: SkillInput, state: AgentState = None) -> SkillOutput:
        """
        Execute the skill with validated input.
        
        Note: state parameter allows skills to inherit context (e.g., chunk_index, title_k)
        from AgentState rather than requiring LLM to specify them.
        """
        ...

## State Inheritance: Infrastructure Parameters

**Design Principle**: Infrastructure parameters (like `chunk_index`, `title_k`) should be inherited from `AgentState`, not exposed to LLM as skill inputs.

**Why**:
- LLM should reason about **semantic parameters** (queries, top_k), not infrastructure details
- Infrastructure config (`search_config`) is set once at workflow initialization
- Reduces LLM confusion and prevents incorrect index names in tool calls
- Keeps skill interface focused on what LLM can meaningfully reason about

**Implementation**:
1. Remove `chunk_index` and `title_k` from skill input models
2. Pass `state: AgentState` to `execute()` method
3. Extract infrastructure values from `state["search_config"]` during execution
4. LLM only sees semantic parameters in tool schema

**Example**:
```python
# ❌ Bad: LLM must specify chunk_index
class GeneralSearchInput(SkillInput):
    query_list: list[str]
    chunk_index: str  # LLM shouldn't need to know this

# ✅ Good: chunk_index inherited from state
class GeneralSearchInput(SkillInput):
    query_list: list[str]  # Only semantic parameters
    # chunk_index comes from state["search_config"]["chunk_index"]

async def execute(self, input_data: GeneralSearchInput, state: AgentState) -> GeneralSearchOutput:
    chunk_index = state["search_config"]["chunk_index"]  # Inherited
    title_k = state["search_config"]["title_k"]  # Inherited
    # ... use inherited values
```

## Capability Meta-Model (Future: Planner / Skill Graph / Auto Reasoning)

`SkillRegistry` today is primarily a **capability container**:
- `get_all_tool_schemas()`
- `get_skill_descriptions()`

This is sufficient for "LLM can use skills", but it is **not yet a capability meta-model**.
Without structured metadata, a future Planner / Skill Graph has to rely on natural language `description`,
which makes planning brittle.

To make skills *plannable* (not just usable), extend `BaseSkill` with structured capability metadata:

```python
from typing import Literal, Optional

CapabilityType = Literal["retrieval", "refinement", "analysis"]
OutputType = Literal["documents", "chunks", "summary", "artifact"]
CostLevel = Literal["low", "medium", "high"]

class BaseSkill(ABC):
    """
    Capability meta-model (planner-friendly).

    Motivation: enable deterministic routing, cost-aware planning, skill graphs,
    and precondition checking without relying only on natural language.
    """

    # What the skill *is* (for planners)
    capability_type: CapabilityType = "retrieval"
    output_type: OutputType = "documents"
    cost_level: CostLevel = "low"

    # What the skill *needs / assumes*
    capability_tags: set[str] = set()
    preconditions: list[str] = []
    requires_context: list[str] = []

    # What the skill *produces* (beyond immediate output)
    produces_artifact_type: Optional[str] = None
```

Recommended next step for `SkillRegistry` (when moving toward planners):
- Add `get_capability_index()` to return these fields in a structured form
- Add optional filters like `list_by(capability_type=..., output_type=..., cost_level=...)`

# lib/skills/general_search.py
from pydantic import BaseModel, Field
from lib.search.elastic_mix import ElasticMix
from lib.agentic.config import AgentState
from typing import Literal

class GeneralSearchInput(BaseModel):
    """Input schema for general document search.
    
    Note: chunk_index and title_k are NOT included here - they are inherited
    from state["search_config"] during execution. This prevents LLM from needing
    to specify infrastructure details.
    """
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
    # chunk_index and title_k are inherited from state, not LLM input

class DocumentResult(BaseModel):
    """Single search result document."""
    doc_id: str
    chunk_id: str
    text: str
    doc_title: str
    score: float
    index: int = 0

class GeneralSearchOutput(BaseModel):
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
    
    async def execute(
        self, 
        input_data: GeneralSearchInput, 
        state: AgentState = None
    ) -> GeneralSearchOutput:
        """Execute general search with validated input.
        
        Infrastructure parameters (chunk_index, title_k) are inherited from state,
        not from LLM input. This keeps the skill interface focused on semantic
        parameters that LLM should reason about.
        """
        if state is None:
            raise ValueError("state is required to inherit chunk_index and title_k")
        
        # Inherit infrastructure config from state (not from LLM input)
        search_config = state.get("search_config", {})
        chunk_index = search_config.get("chunk_index", "miles_guo")
        title_k = search_config.get("title_k", 3)
        
        # Create MCP request - title_index is derived from chunk_index in MCP layer
        mcp_request = GeneralSearchRequest(
            query_list=input_data.query_list,
            chunk_index=chunk_index,
            top_k=input_data.top_k,
            title_k=title_k
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

# lib/skills/doc_search.py
class DocumentSearchInput(BaseModel):
    """Input schema for document-specific search."""
    query: str = Field(..., description="Search query")
    doc_id: str = Field(..., description="Document ID to search within")
    top_k: int = Field(default=5, ge=1, le=20)
    collection: str = Field(default="default")

class DocumentSearchOutput(BaseModel):
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
    
    def __init__(self, elastic_mix: ElasticMix):
        self.elastic_mix = elastic_mix
    
    async def execute(self, input_data: DocumentSearchInput) -> DocumentSearchOutput:
        """Execute document-specific search."""
        collection_map = {
            "default": ("miles_guo_titles", "miles_guo"),
        }
        _, chunk_index = collection_map.get(
            input_data.collection,
            collection_map["default"]
        )
        
        raw_results = await self.elastic_mix.search_doc(
            input_data.query,
            input_data.doc_id,
            chunk_index=chunk_index,
            chunk_k=input_data.top_k
        )
        
        results = [
            DocumentResult(**r, index=i)
            for i, r in enumerate(raw_results)
        ]
        
        return DocumentSearchOutput(
            results=results,
            doc_id=input_data.doc_id,
            total_found=len(results)
        )

# lib/skills/registry.py
from typing import Dict, List

class SkillRegistry:
    """Registry for agent-native skills with tool export capabilities."""
    
    def __init__(self):
        self._skills: Dict[str, BaseSkill] = {}
    
    def register(self, skill: BaseSkill):
        """Register a skill."""
        self._skills[skill.name] = skill
    
    def get(self, name: str) -> BaseSkill:
        """Get a skill by name."""
        if name not in self._skills:
            raise ValueError(f"Skill '{name}' not found. Available: {self.list_available()}")
        return self._skills[name]
    
    def list_available(self) -> List[str]:
        """List all available skill names."""
        return list(self._skills.keys())
    
    def get_all_tool_schemas(self) -> List[dict]:
        """Get all skills as OpenAI tool schemas for LLM function calling."""
        return [skill.to_tool_schema() for skill in self._skills.values()]
    
    def get_all_mcp_tools(self) -> List[dict]:
        """Get all skills as MCP tool specifications."""
        return [skill.to_mcp_tool_spec() for skill in self._skills.values()]
    
    def get_skill_descriptions(self) -> Dict[str, str]:
        """Get skill names and descriptions for LLM planning."""
        return {
            name: skill.description
            for name, skill in self._skills.items()
        }

# lib/agentic/nodes/rag_search_node.py (modernized with LLM-driven skill selection)
async def rag_search_node_with_llm_selection(
    state: AgentState,
    skill_registry: SkillRegistry,
    llm_client
) -> AgentState:
    """
    Modern agent node where LLM selects and calls skills dynamically.
    
    This represents the shift from "pre-planned search_ops" to
    "LLM-driven capability selection".
    """
    question = state["question"]
    context = state.get("context", {})
    
    # Get available skills as tools
    available_tools = skill_registry.get_all_tool_schemas()
    skill_descriptions = skill_registry.get_skill_descriptions()
    
    # LLM selects which skill(s) to use based on question
    prompt = f"""
    User question: {question}
    Context: {context}
    
    Available search capabilities:
    {json.dumps(skill_descriptions, indent=2, ensure_ascii=False)}
    
    Select and call the appropriate search skill(s) to answer the question.
    """
    
    # Call LLM with tool calling
    response = await llm_client.call_with_tools(
        prompt,
        tools=available_tools,
        tool_choice="auto"
    )
    
    # Execute selected skills
    results = []
    if response.get("tool_calls"):
        for tool_call in response["tool_calls"]:
            skill_name = tool_call["function"]["name"]
            skill = skill_registry.get(skill_name)
            
            # Parse and validate input
            input_data = skill.input_model.model_validate_json(
                tool_call["function"]["arguments"]
            )
            
            # Execute skill
            output = await skill.execute(input_data)
            results.append(output.model_dump())
    
    return {**state, "search_results": results}

# Alternative: Traditional search_ops-based approach (backward compatible)
async def rag_search_node_with_skills(
    state: AgentState,
    skill_registry: SkillRegistry
) -> AgentState:
    """
    Execute pre-planned search operations using skills.
    This maintains backward compatibility with existing search_ops structure.
    """
    search_ops = state.get("search_ops", [])
    results = []
    
    for op in search_ops:
        skill_name = op["type"]
        skill = skill_registry.get(skill_name)
        
        # Validate input using skill's input model
        input_data = skill.input_model.model_validate(op)
        
        # Execute skill
        output = await skill.execute(input_data)
        results.append(output.model_dump())
    
    return {**state, "search_results": results}
```

## Key Features of Modern Agent Skills

| Feature | Implementation |
|---------|---------------|
| **Structured Input Schema** | ✅ Pydantic models with validation |
| **Structured Output Schema** | ✅ Pydantic models for type safety |
| **Tool Schema Export** | ✅ `to_tool_schema()` for OpenAI function calling |
| **MCP Tool Export** | ✅ `to_mcp_tool_spec()` for MCP integration |
| **LLM-Readable Descriptions** | ✅ Rich descriptions for capability understanding |
| **Dynamic Skill Selection** | ✅ LLM can select skills based on context |
| **Composable Reasoning Units** | ✅ Skills are cognitive capabilities, not just functions |

## Benefits

- **Agent-native**: Skills are visible to LLMs as capabilities, not just internal functions
- **Type-safe**: Pydantic models ensure correct inputs/outputs
- **LLM-callable**: Can be directly used in function calling workflows
- **MCP-compatible**: Can be exported as standardized MCP tools
- **Planner-friendly**: LLMs can reason about which skills to use
- **Extensible**: Easy to add new skills with clear boundaries
- **Testable**: Structured inputs/outputs make testing straightforward

## Architecture Evolution

```
Old: Pre-planned search_ops → Execute functions
     (Strategy Pattern - internal implementation detail)

New: LLM reasoning → Select skills → Execute skills → Observe → Reason again
     (Cognitive Capability Layer - agent-visible abilities)
```

## Integration Plan: Using Skills in reply_validation_node

### Current State

Currently, `reply_validation_node` generates `search_ops` in a legacy format:
- `{"type": "search_general", "query_list": [...]}`
- `{"type": "search_doc", "query": "...", "doc_id": "..."}`
- `{"type": "search_neighbour_chunks", "doc_id": "...", "chunk_id": "...", "distance": ...}`

These `search_ops` are then executed in `rag_search_node` using `SearchService` (MCP layer).

### Migration Strategy

#### Direct Skill Calling

**Concept**: Let LLM directly call skills via tool calling, eliminating the need for intermediate `search_ops` format.

**Implementation**:
1. Pass `SkillRegistry` to `reply_validation_node`
2. Replace the `validate_and_refine` tool with skill tools from registry
3. LLM can call skills directly when `type_state == "refine_query"`
4. Do **not** execute skills inside `reply_validation_node` (keep it a reasoning/validation node)
5. Persist the tool calls (skill invocations) into state for a dedicated execution node
6. Keep the agent loop explicit: Reasoning → Execution → Observation → Reasoning

**Benefits**:
- Direct agent-native capability selection
- Type-safe skill execution with Pydantic validation
- Eliminates format conversion overhead
- LLM sees skills as capabilities, not internal operations

**Code Structure**:
```python
async def reply_validation_node(
    state: AgentState,
    skill_registry: SkillRegistry
) -> AgentState:
    """
    Validate answer and (when needed) plan skill calls via tool calling.

    Important: do NOT execute skills here. Emit planned tool calls into state so a
    dedicated execution node can run them and feed observations back into the loop.
    """
    # Get available skills as tools
    available_tools = skill_registry.get_all_tool_schemas()
    
    # Add validation tool (validate_and_refine)
    tools = [validation_tool] + available_tools
    
    # LLM can either:
    # 1. Call validate_and_refine with type_state="valid_answer"
    # 2. Call validate_and_refine with type_state="refine_query" AND call skills directly
    
    # Persist planned skill calls for the next node (execution)
    planned_skill_calls = [
        tc for tc in response.get("tool_calls", [])
        if tc.get("function", {}).get("name") in skill_registry.list_available()
    ]

    return {**state, "planned_skill_calls": planned_skill_calls}
```

### Implementation Approach

**Direct Skill Calling** is chosen because:
- Aligns with agent-native architecture
- LLM directly reasons about capabilities
- Eliminates intermediate format conversion
- Better type safety end-to-end

**Migration Steps**:
1. Add `SkillRegistry` parameter to `reply_validation_node`
2. Modify tool definitions to include skill tools alongside validation tool
3. Update LLM prompt to encourage direct skill calling when refining
4. Add a dedicated `skill_execution_node` that consumes `planned_skill_calls` and executes them
5. Store execution outputs as `observations` (or `search_results`) in state
6. Route back to a reasoning node (e.g., `rag_reply_node` / planner node) to interpret observations
7. Remove `search_ops` format once fully migrated

**Skill Execution Node Example**:
```python
async def skill_execution_node(
    state: AgentState,
    skill_registry: SkillRegistry
) -> AgentState:
    """
    Execute planned skill calls from reply_validation_node.
    
    Important: Pass state to skill.execute() so infrastructure parameters
    (chunk_index, title_k) can be inherited from state["search_config"].
    """
    planned_skill_calls = state.get("planned_skill_calls", [])
    search_results = []
    
    for tool_call in planned_skill_calls:
        skill_name = tool_call["function"]["name"]
        skill = skill_registry.get(skill_name)
        
        # Parse and validate input (only semantic parameters, no chunk_index)
        input_data = skill.input_model.model_validate_json(
            tool_call["function"]["arguments"]
        )
        
        # Execute skill with state for infrastructure inheritance
        output = await skill.execute(input_data, state=state)
        search_results.append(output.model_dump())
    
    return {**state, "search_results": search_results}
```

### Backward Compatibility

During transition:
- Keep `search_ops` in state for compatibility if needed
- Gradually migrate nodes to skill-based approach
- Remove legacy `search_ops` format after full migration

### Avoiding a "Super Node" (Preserving the Agent Loop)

Executing skills inside `reply_validation_node` can collapse the loop into a single oversized node:

- Bad: Reasoning (LLM) → Execute Skills → Return (looks like "LLM → Execute → End")
- Good: Reasoning (LLM) → Skill Execution Node → Observation → Reasoning (LLM) → ...

Recommended node split (conceptual):
- **Planner / Reasoning Node**: decides *what to do next* (emits `planned_skill_calls`)
- **Skill Execution Node**: executes skills (produces `observations`)
- **Validation Node**: decides whether to stop or continue the loop

## Files to Create

- `lib/skills/__init__.py`
- `lib/skills/base.py` - BaseSkill with tool export capabilities
- `lib/skills/general_search.py` - General search skill with schemas
- `lib/skills/doc_search.py` - Document-specific search skill
- `lib/skills/neighbour_search.py` - Neighbour chunk search skill
- `lib/skills/registry.py` - Registry with tool export methods

