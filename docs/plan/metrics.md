# Metrics: Offline Evaluation Framework

## Goal

Define a repeatable **on-demand** offline evaluation loop for RAG quality, used
only at special moments (before a major search/prompt/model change, or when
debugging a suspected regression). This is **not** a per-commit CI gate.

## Scope

- End-to-end answer quality via LLM-as-judge, multi-dimension scoring.
- Retrieval quality against the source chunk the question was generated from.

---

## 1. Gold Data: Self-Generated From Single Documents

We do not hand-label answers. Instead, gold pairs are generated from the corpus:

1. Sample chunks from an index (e.g. `miles_guo`, `lzj`, `lxb`, `mzd`,
   `epstein9`). Chunks are readable via the existing chunk store in
   `lib/search/elastic_chunk_index.py` (`ElasticWriteClientChunks`), or directly
   from the on-disk chunk files used to build the index.
2. For each chunk, call the LLM to produce a **(query, gold_answer)** pair that is
   answerable *from that chunk alone*. Reuse `call_llm(...)` in
   `lib/llm/litellm_api.py` with a JSON `response_format`.
3. Record the source `doc_id` / `chunk_id` alongside the pair — this is the
   retrieval ground truth (the chunk that *should* be retrieved).

Each benchmark row:

```json
{
  "id": "miles_guo_00123",
  "index": "miles_guo",
  "source_doc_id": "...",
  "source_chunk_id": "...",
  "query": "generated question",
  "gold_answer": "generated reference answer"
}
```

Store as versioned JSONL under `test/eval_data/<index>_vN.jsonl`. Regenerate only
when the corpus changes; keep old versions for comparison.

### Generation quality guard

Auto-generated pairs are noisy. Add a cheap filter step: drop pairs where the
generator flags the chunk as un-answerable, too short, or purely tabular. This
keeps the benchmark honest without manual labeling.

---

## 2. End-to-End Scoring: LLM-as-Judge, Multi-Dimension

For each benchmark row:

1. Run the real pipeline to get a candidate answer:
   - RAG path: `lib/rag/rag_base.py` (retrieval + answer prompt).
   - Optionally the agentic path via `lib/agentic/graph.py` for comparison.
2. Call an LLM judge (again `call_llm` with a strict JSON `response_format`) that
   scores the candidate against `gold_answer` **and** the retrieved context on
   several dimensions, each `0-5`:

   | Dimension        | Question the judge answers                                  |
   |------------------|-------------------------------------------------------------|
   | Correctness      | Does the answer match the gold answer's facts?              |
   | Completeness     | Does it cover the key points, without major omissions?      |
   | Faithfulness     | Is every claim grounded in the retrieved context (no hallucination)? |
   | Relevance        | Does it actually answer the question, without padding?      |

   The dimension set is configurable — start with these four; add/remove per need.

3. **Total score** = weighted sum of the dimensions (default: equal weights,
   normalized to `0-100`). The judge returns per-dimension scores + a one-line
   rationale so failures are inspectable.

Judge output schema:

```json
{
  "correctness": 4,
  "completeness": 3,
  "faithfulness": 5,
  "relevance": 4,
  "total": 80,
  "rationale": "…"
}
```

### Judge reliability notes

- Pin the judge model and prompt; a changed judge invalidates cross-run
  comparison.
- Use a stronger model for the judge than for the answer when possible.
- Judge is stochastic: run it at `temperature=0` and treat single-point scores as
  approximate. Report aggregate (mean per dimension) over the whole set, not
  per-row verdicts.

---

## 3. Retrieval Scoring

Because each query carries its `source_chunk_id`, retrieval is measurable without
a judge. Run the search entry `ElasticMix.search(query_list, title_index,
chunk_index, ...)` (or `search_naive`) in `lib/search/elastic_mix.py` and check
where the source chunk lands:

- **Recall@K** — is `source_chunk_id` in the top-K hits?
- **MRR** — reciprocal rank of the source chunk.
- **Context precision** — fraction of retrieved chunks that are actually relevant
  (approximate via the judge's faithfulness signal, or skip initially).

Retrieval metrics are cheap (no answer-LLM call) and catch most regressions, so
they are the primary signal; run them first.

---

## 4. Implementation Anchors

Proposed layout (new `lib/eval/` package + reuse of existing entries):

```
lib/eval/
  dataset_gen.py   # sample chunks -> (query, gold_answer) via call_llm; write JSONL
  judge.py         # LLM-as-judge, multi-dimension JSON scoring
  retrieval.py     # Recall@K / MRR / context precision against source_chunk_id
  run_eval.py      # orchestrator: load JSONL -> run pipeline -> judge -> aggregate
test/eval_data/
  <index>_vN.jsonl # versioned benchmark rows
```

Wiring to existing code:

| Need                | Reuse                                                        |
|---------------------|-------------------------------------------------------------|
| Read chunks         | `lib/search/elastic_chunk_index.py` (`ElasticWriteClientChunks`) |
| Retrieval           | `lib/search/elastic_mix.py` → `ElasticMix.search` / `search_naive` |
| Answer generation   | `lib/rag/rag_base.py` (RAG) / `lib/agentic/graph.py` (agentic) |
| Any LLM call        | `lib/llm/litellm_api.py` → `call_llm(str1, model_name=..., response_format=...)` |
| Tracing (optional)  | `lib/observability/langsmith.py` — wrap eval runs with `@traced` if `langsmith_enabled()` |

### How to run

Manual, on demand — not in per-commit CI:

```bash
# 1. (re)generate benchmark for one index
poetry run python -m lib.eval.dataset_gen --index miles_guo --n 100

# 2. run retrieval-only (fast) or full end-to-end eval
poetry run python -m lib.eval.run_eval --index miles_guo --mode retrieval
poetry run python -m lib.eval.run_eval --index miles_guo --mode full
```

Prints an aggregate report (per-dimension means, total, Recall@K, MRR). Keep the
existing `pytest` suite in `test/` for correctness; evaluation stays a separate
manual script so it never blocks commits.

---

## 5. Baseline and Acceptance

- Save each run's aggregate JSON next to the benchmark (`test/eval_data/`) so two
  runs can be diffed by hand.
- Before a major change, record a baseline run; after, compare deltas.
- Acceptance for a change to land: no meaningful regression in Recall@K and
  end-to-end total vs. baseline on the affected index(es).
- Categorize failures by cause for triage: retrieval miss / reasoning error /
  formatting error.
