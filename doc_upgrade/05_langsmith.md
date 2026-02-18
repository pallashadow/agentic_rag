# LangSmith Monitoring Upgrade Runbook

## Goal

Upgrade this project to LangSmith observability with minimal risk, so we can track:

- Request-level traces (`/chatbot`, `/agentic_rag`, streaming endpoints)
- LangGraph execution path (node loop, retry, iteration)
- LiteLLM model calls (model name, fallback path, latency, token usage)
- Production troubleshooting metadata (query type, search count, endpoint, version)

This document is an execution runbook, not only design notes.

## Current Architecture (Relevant to This Upgrade)

- API entry: `main.py`
- Graph orchestration: `lib/agentic/graph.py`
- LLM calls and fallback router: `lib/llm/litellm_api.py`
- Logging setup: `lib/app_logger.py`

The project already has `langsmith` in `poetry.lock`, but tracing is not wired in code yet.

## Phase 0: Prerequisites

1. Create or confirm a LangSmith workspace.
2. Generate API Key (Personal or Service Key).
3. Decide project naming convention, for example:
   - `chatbot-milesguo-dev`
   - `chatbot-milesguo-staging`
   - `chatbot-milesguo-prod`
4. Decide privacy policy for prompt logging (masking/redaction rules).

## Phase 1: Environment Configuration

Add these environment variables to `.env` and deployment environments:

```bash
LANGSMITH_API_KEY=lsv2_xxx
LANGSMITH_TRACING=true
LANGSMITH_PROJECT=chatbot-milesguo-dev
LANGSMITH_ENDPOINT=https://api.smith.langchain.com
APP_ENV=dev
APP_VERSION=2026-02-18
```

Notes:

- `LANGSMITH_TRACING=true` enables automatic tracing for supported LangChain/LangGraph paths.
- `LANGSMITH_PROJECT` should vary by environment; do not mix dev/prod traces.
- Keep `APP_ENV` and `APP_VERSION` for trace metadata and release diagnostics.

## Phase 2: Add a Unified Tracing Helper

Create a thin wrapper module, for example: `lib/observability/langsmith.py`.

Responsibilities:

- Detect if LangSmith is enabled (`LANGSMITH_TRACING`, `LANGSMITH_API_KEY`)
- Provide `is_enabled()`
- Provide a unified decorator/helper for endpoint and function tracing
- Centralize metadata tags (`env`, `version`, `service`)

Suggested helper shape:

```python
import os
from langsmith import traceable

def langsmith_enabled() -> bool:
    return (
        os.getenv("LANGSMITH_TRACING", "false").lower() == "true"
        and bool(os.getenv("LANGSMITH_API_KEY"))
    )

def traced(run_type: str, name: str):
    if not langsmith_enabled():
        def passthrough(fn):
            return fn
        return passthrough
    return traceable(run_type=run_type, name=name)
```

Why this phase is important:

- Avoid scattering direct LangSmith conditions across business code
- Keep tracing behavior consistent for all entrypoints
- Make rollback easy (single module switch)

## Phase 3: Instrument API Entrypoints in `main.py`

Target endpoints first:

- `/chatbot`
- `/chatbot_stream`
- `/agentic_rag`
- `/agentic_rag_stream`
- Optional: `/search`, `/mcp/search`

Execution steps:

1. Add a trace wrapper around endpoint handlers (or around core work blocks).
2. Attach metadata:
   - `endpoint`
   - `chunk_index`
   - `title_k`, `chunk_k`, `query_expand_k`
   - `has_context` (bool)
3. Add tags:
   - `api`
   - `stream` / `non-stream`
   - `agentic` / `rag`

Minimum acceptance for this phase:

- Every request to the target endpoint appears as one top-level LangSmith run.

## Phase 4: Instrument LiteLLM Calls in `lib/llm/litellm_api.py`

Critical functions:

- `call_llm`
- `call_llm_stream`
- `call_llm_with_tools`
- `call_llm_stream_with_fallback`

Execution steps:

1. Wrap each function with trace helper or explicit child span.
2. Record request metadata:
   - `model_name`
   - `response_format` type (`json_schema` vs plain text)
   - `tool_count` and `tool_choice` for tool-calling requests
3. Record fallback behavior:
   - primary model
   - fallback model
   - fallback trigger error type
4. Record response metadata:
   - latency
   - token usage if available from provider response

Why this phase matters:

- You can diagnose "why fallback happened"
- You can compare quality/cost between `gpt` and `gemini` routes
- You can detect structured-output parse failures quickly

## Phase 5: Add LangGraph-Level Metadata

`AgenticGraph` is built in `lib/agentic/graph.py` and invoked in `main.py`.

Execution steps:

1. When calling `agentic_base.ainvoke(state1)`, pass run configuration metadata/tags.
2. Include fields useful for debugging loop behavior:
   - `max_iter`
   - `search_count` (post-run)
   - `query_type` (post-run)
3. Keep metadata lightweight; avoid raw full documents.

Expected result:

- LangSmith trace can show both graph-level run and child LLM/tool runs.

## Phase 6: Privacy and Redaction Guardrails

Before production rollout, define redaction policy:

- Mask keys/tokens from inputs and metadata
- Optionally trim long user content
- Exclude internal secrets from custom metadata

Recommended implementation:

- Add a sanitization function in `lib/observability/langsmith.py`
- Apply sanitization before attaching metadata/tags

## Phase 7: Local Verification Checklist

Run verification in this order:

1. Start service with LangSmith env enabled.
2. Call non-stream endpoint:
   - `GET /chatbot?...`
3. Call stream endpoint:
   - `GET /agentic_rag_stream?...`
4. Trigger at least one fallback scenario (primary model unavailable or forced failure).
5. Open LangSmith UI and confirm:
   - top-level runs exist
   - nested spans exist
   - metadata contains endpoint/model/fallback markers
   - no sensitive fields leaked

Pass criteria:

- Trace coverage >= 90% for target endpoints and LLM call paths.

## Phase 8: Staging Rollout

1. Deploy to staging with `LANGSMITH_PROJECT=chatbot-milesguo-staging`.
2. Run smoke tests:
   - chatbot normal flow
   - agentic loop flow
   - streaming flow
3. Monitor for 24h:
   - trace ingest stability
   - latency overhead
   - missing trace rate

Rollback rule:

- If observability causes instability, set `LANGSMITH_TRACING=false` and redeploy.

## Phase 9: Production Rollout

1. Enable in prod with separate project:
   - `LANGSMITH_PROJECT=chatbot-milesguo-prod`
2. Start with partial traffic (if available).
3. Observe first 48h:
   - trace completeness
   - fallback anomaly rate
   - endpoint error correlations

Success criteria:

- Production incidents can be traced from API request -> graph step -> model call.

## Recommended File Changes (Implementation Map)

- Create:
  - `lib/observability/langsmith.py`
- Modify:
  - `main.py` (endpoint-level tracing and metadata)
  - `lib/llm/litellm_api.py` (model/fallback/tool tracing)
  - Optional: `lib/agentic/graph.py` or invoke site in `main.py` for graph metadata
  - `env.example` (LangSmith variables)

## Minimal Delivery Scope (MVP)

If you want the fastest usable version, implement only:

1. Env vars
2. Endpoint top-level traces for `/chatbot` and `/agentic_rag`
3. `call_llm` + `call_llm_with_tools` tracing
4. Fallback marker in `call_llm_stream_with_fallback`

This already covers most debugging value with low code churn.

## Post-Upgrade KPIs

Track weekly:

- Trace coverage rate (requests with trace / total requests)
- Mean trace latency overhead
- Fallback frequency by model
- Structured-output parse failure rate
- MTTR for LLM-related incidents

