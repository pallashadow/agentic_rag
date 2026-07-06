# Project Plan: Remaining Upgrades

Modernization / LangChain-alternative work. The completed items (LangChain usage
analysis, native function calling, MCP integration, skill system, LangSmith
observability) have shipped and their design notes were removed. Only open items
remain:

## Open Items

1. TODO **[Hansard index](hansard-index.md)** — add a UK Parliament Hansard
   (English, ~3–5M words) `chunk_index` so the demo is legible to a UK audience,
   reusing the existing download → chunk → summary/title → Elasticsearch pipeline.
2. TODO **[Metrics](metrics.md)** — on-demand offline evaluation framework:
   self-generated gold data, LLM-as-judge multi-dimension scoring, and retrieval
   metrics (Recall@K / MRR).
3. TODO **[Frontend → React](frontend-react.md)** — migrate the static
   `frontend/` HTML+TS pages to a React app.
