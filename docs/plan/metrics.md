# Metrics: Simple Offline RAG Evaluation

## Goal

A small, repeatable check to run before/after a retrieval, prompt, or model change,
or when chasing a regression. Not a CI gate.

It answers two questions with a handful of numbers:

1. **Retrieval** — did search return the answer chunk?
2. **Answer** — given that context, is the reply correct and faithful?

Keep the two separate so you can see which one moved.

---

## 1. Build a question set (once)

No one builds it by hand — the `dataset_gen.py` script generates it automatically.
Steps:

1. **Read chunks** from Elasticsearch with `ElasticReadClientChunks`
   (`lib/search/elastic_chunk_index.py`). Do not use the `Write` client — that one
   is for indexing.
2. **Sample** ~200 chunks with a fixed `seed`, at most ~2 per document; skip empty /
   too-short / garbage chunks.
3. **Generate a question** per chunk with `call_llm`, prompting roughly: *"Here is a
   passage: {chunk}. Write one question answerable only from it, and give the
   answer."* Require structured JSON `{"q": ..., "gold": ...}`.
4. **Save** `q`, `gold`, and the chunk's `doc_id` / `chunk_id` to
   `test/eval_data/<index>.jsonl` and commit it.

```json
{"id": "miles_guo_001", "q": "...", "gold": "...", "doc_id": "doc-1", "chunk_id": "17"}
```

Because each question is derived from a known chunk, its source `(doc_id, chunk_id)`
is the retrieval ground truth for free — no separate labeling.

Rules:
- Same `seed` + same corpus → same sampled chunks.
- Optional: eyeball the generated file once and delete obviously broken rows.

That's the whole dataset. No hashes, manifests, or multi-model validation.

---

## 2. Retrieval eval → three numbers

Run the production search and check whether the source chunk came back.

```python
hits, _ = await RAGBase().search(row["q"], chunk_index=index, chunk_k=10, query_expand_k=0)
hit = any(h["doc_id"] == row["doc_id"] and h["chunk_id"] == row["chunk_id"] for h in hits)
```

Report:
- **Recall@10** — fraction of rows where the source `(doc_id, chunk_id)` was
  returned. A failed/errored row counts as a miss.
- **Doc Recall@10** — same but matching `doc_id` only. Separates "wrong document" from
  "right document, wrong chunk".
- **no-hit rate** — fraction of rows where search returned nothing. Spikes when
  retrieval is broken.

(Only whole-set membership — the search path doesn't rank by relevance, so
rank-based metrics like MRR aren't meaningful here.)

---

## 3. Answer eval → four numbers

Run the full RAG reply, then have one LLM judge score it.

```python
result = await RAGBase().chat(row["q"], chunk_index=index, query_expand_k=0)
answer = result["content"]
```

Judge call: strict JSON, `temperature=0`. It sees the question, gold answer,
candidate answer, and retrieved context, and returns four 0–5 scores in one call:

```json
{"correctness": 4, "faithfulness": 5, "completeness": 3, "relevance": 4}
```

- **Correctness** — candidate agrees with the gold answer.
- **Faithfulness** — every claim is supported by the retrieved context (no making
  things up).
- **Completeness** — covers the key points the answer needs.
- **Relevance** — answers the question without padding or going off-topic.

Report the mean of each across all rows. Keep them separate — don't blend into one
score, or you lose which dimension moved.

Optionally record `latency` and answer length per row (no LLM needed) — handy for
catching performance regressions.

---

## 4. Compare against a baseline

Save a run's numbers as the baseline. After a change, rerun and print old vs new
side by side.

```text
metric            baseline   candidate   delta
recall@10           0.78       0.81      +0.03
doc_recall@10       0.90       0.91      +0.01
no-hit rate         0.02       0.02       0.00
correctness         4.10       4.05      -0.05
faithfulness        4.40       4.38      -0.02
completeness        3.80       3.82      +0.02
relevance           4.30       4.29      -0.01
```

Eyeball it. A meaningful drop (say correctness down > 0.2, or recall down > 0.05) is
a regression worth investigating. No bootstrap, CI, or pass/fail exit codes — just
the numbers and your judgement.

Print the worst-scoring rows (question, retrieved chunks, answer) so regressions are
easy to inspect.

---

## 5. Layout

```text
lib/eval/
  dataset_gen.py   # sample chunks + generate questions -> eval_data/<index>.jsonl
  run_eval.py      # run search/chat, score, print numbers, compare to baseline
test/eval_data/
  <index>.jsonl        # committed question set
  <index>.baseline.json # saved baseline numbers
```

Two files. Metric functions stay pure; adapters just call the existing
`RAGBase.search` / `RAGBase.chat`.

---

## 6. Commands

```bash
# Build the question set.
poetry run python -m lib.eval.dataset_gen --index miles_guo --n 200 --seed 42

# Run retrieval + answer eval, print numbers.
poetry run python -m lib.eval.run_eval --index miles_guo

# Save this run as the baseline.
poetry run python -m lib.eval.run_eval --index miles_guo --save-baseline

# Compare against the saved baseline.
poetry run python -m lib.eval.run_eval --index miles_guo --baseline
```

## Later (only if needed)

Add these one at a time when a real need shows up — not now:
query expansion eval, the agentic pipeline, more judge dimensions, statistical
confidence intervals, corpus-change tracking.
