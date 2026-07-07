"""Run the offline RAG eval: retrieval metrics + LLM-judged answer scores.

Loads the question set built by ``dataset_gen.py``, runs the production
``RAGBase.search`` / ``RAGBase.chat`` paths, scores answers with a single LLM
judge call per row, and prints a small table of numbers. Optionally saves the
run as a baseline or compares against a saved one.

See ``docs/plan/metrics.md`` for the design.

Usage:
    poetry run python -m lib.eval.run_eval --index miles_guo
    poetry run python -m lib.eval.run_eval --index miles_guo --save-baseline
    poetry run python -m lib.eval.run_eval --index miles_guo --baseline
"""

import argparse
import asyncio
import json
import time
from pathlib import Path

from lib.rag.rag_base import RAGBase
from lib.index_mapping import get_index_meta
from lib.llm.litellm_api import call_llm_with_fallback
from lib.app_logger import get_logger

logger = get_logger(__name__)

EVAL_DATA_DIR = Path(__file__).resolve().parents[2] / "test" / "eval_data"

CHUNK_K = 10
JUDGE_DIMS = ["correctness", "faithfulness", "completeness", "relevance"]

_JUDGE_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "judge_scores",
        "schema": {
            "type": "object",
            "properties": {d: {"type": "integer", "minimum": 0, "maximum": 5} for d in JUDGE_DIMS},
            "required": JUDGE_DIMS,
            "additionalProperties": False,
        },
    },
}


def _load_rows(index: str) -> list[dict]:
    path = EVAL_DATA_DIR / f"{index}.jsonl"
    if not path.exists():
        raise SystemExit(f"Question set not found: {path}\nRun dataset_gen first.")
    rows = []
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                rows.append(json.loads(line))
    return rows


async def _eval_retrieval(rag: RAGBase, rows: list[dict], index: str, doc_lang: str,
                          sem: asyncio.Semaphore) -> dict:
    """Recall@k / doc-recall@k / no-hit rate over the whole set."""
    async def _one(row: dict) -> tuple[bool, bool, bool]:
        async with sem:
            try:
                hits, _ = await rag.search(
                    row["q"], chunk_index=index, chunk_k=CHUNK_K,
                    query_expand_k=0, doc_lang=doc_lang, query_lang=doc_lang,
                )
            except Exception as e:
                logger.warning("Search failed for %s: %s", row.get("id"), e)
                return (False, False, True)  # errored row = miss + no-hit
        no_hit = len(hits) == 0
        chunk_hit = any(
            str(h["doc_id"]) == str(row["doc_id"]) and str(h["chunk_id"]) == str(row["chunk_id"])
            for h in hits
        )
        doc_hit = any(str(h["doc_id"]) == str(row["doc_id"]) for h in hits)
        return (chunk_hit, doc_hit, no_hit)

    results = await asyncio.gather(*[_one(r) for r in rows])
    n = len(results) or 1
    return {
        "recall@10": sum(r[0] for r in results) / n,
        "doc_recall@10": sum(r[1] for r in results) / n,
        "no-hit rate": sum(r[2] for r in results) / n,
    }


async def _judge(row: dict, answer: str, context: str) -> dict | None:
    prompt = (
        "You are grading a RAG answer. Score each dimension 0-5 (integer).\n\n"
        f"Question:\n{row['q']}\n\n"
        f"Gold answer:\n{row['gold']}\n\n"
        f"Candidate answer:\n{answer}\n\n"
        f"Retrieved context:\n{context}\n\n"
        "Dimensions:\n"
        "- correctness: candidate agrees with the gold answer.\n"
        "- faithfulness: every claim is supported by the retrieved context.\n"
        "- completeness: covers the key points the answer needs.\n"
        "- relevance: answers the question without padding or going off-topic.\n\n"
        'Return JSON: {"correctness": <0-5>, "faithfulness": <0-5>, '
        '"completeness": <0-5>, "relevance": <0-5>}.'
    )
    try:
        result = await call_llm_with_fallback(
            prompt, model_name="gpt", response_format=_JUDGE_SCHEMA
        )
        if isinstance(result, str):
            result = json.loads(result)
        return {d: float(result[d]) for d in JUDGE_DIMS}
    except Exception as e:
        logger.warning("Judge failed for %s: %s", row.get("id"), e)
        return None


async def _eval_answers(rag: RAGBase, rows: list[dict], index: str, doc_lang: str,
                        sem: asyncio.Semaphore) -> tuple[dict, list[dict]]:
    """Judge scores per dimension + per-row detail for inspecting regressions."""
    async def _one(row: dict) -> dict:
        detail = {"id": row.get("id"), "q": row["q"], "scores": None,
                  "answer": "", "latency": 0.0, "context": ""}
        async with sem:
            try:
                start = time.time()
                result = await rag.chat(
                    row["q"], chunk_index=index, chunk_k=CHUNK_K,
                    query_expand_k=0, doc_lang=doc_lang, query_lang=doc_lang,
                )
                detail["latency"] = time.time() - start
                detail["answer"] = result["content"]
                context = "\n---\n".join(
                    h.get("text", "") for h in result.get("search_results", [])
                )
                detail["context"] = context
            except Exception as e:
                logger.warning("Chat failed for %s: %s", row.get("id"), e)
                return detail
        detail["scores"] = await _judge(row, detail["answer"], detail["context"])
        return detail

    details = await asyncio.gather(*[_one(r) for r in rows])

    scored = [d["scores"] for d in details if d["scores"] is not None]
    n = len(scored) or 1
    means = {d: sum(s[d] for s in scored) / n for d in JUDGE_DIMS}
    latencies = [d["latency"] for d in details if d["latency"] > 0]
    means["mean_latency_s"] = sum(latencies) / len(latencies) if latencies else 0.0
    return means, details


def _worst_rows(details: list[dict], k: int = 5) -> list[dict]:
    """Lowest-correctness rows, for eyeballing regressions."""
    scored = [d for d in details if d["scores"] is not None]
    scored.sort(key=lambda d: sum(d["scores"].values()))
    return scored[:k]


def _print_metrics(metrics: dict) -> None:
    print("\n=== Eval results ===")
    for key, val in metrics.items():
        print(f"{key:<18} {val:.3f}")


def _print_comparison(baseline: dict, candidate: dict) -> None:
    print("\n=== Baseline vs candidate ===")
    print(f"{'metric':<18}{'baseline':>10}{'candidate':>12}{'delta':>9}")
    for key in candidate:
        base = baseline.get(key)
        cand = candidate[key]
        if base is None:
            print(f"{key:<18}{'-':>10}{cand:>12.3f}{'-':>9}")
        else:
            print(f"{key:<18}{base:>10.3f}{cand:>12.3f}{cand - base:>+9.3f}")


def _print_worst(details: list[dict]) -> None:
    worst = _worst_rows(details)
    if not worst:
        return
    print("\n=== Worst-scoring rows ===")
    for d in worst:
        print(f"\n[{d['id']}] scores={d['scores']}")
        print(f"  Q: {d['q']}")
        print(f"  A: {d['answer'][:300]}")


async def run(index: str, save_baseline: bool, compare_baseline: bool,
              concurrency: int) -> None:
    rows = _load_rows(index)
    meta = get_index_meta(index)
    doc_lang = meta["doc_lang"]
    rag = RAGBase()
    sem = asyncio.Semaphore(concurrency)

    print(f"Loaded {len(rows)} questions for index '{index}' (doc_lang={doc_lang})")

    retrieval = await _eval_retrieval(rag, rows, index, doc_lang, sem)
    answers, details = await _eval_answers(rag, rows, index, doc_lang, sem)
    metrics = {**retrieval, **answers}

    _print_metrics(metrics)
    _print_worst(details)

    baseline_path = EVAL_DATA_DIR / f"{index}.baseline.json"
    if save_baseline:
        EVAL_DATA_DIR.mkdir(parents=True, exist_ok=True)
        with open(baseline_path, "w", encoding="utf-8") as f:
            json.dump(metrics, f, ensure_ascii=False, indent=2)
        print(f"\nSaved baseline to {baseline_path}")

    if compare_baseline:
        if not baseline_path.exists():
            print(f"\nNo baseline to compare at {baseline_path}. Run with --save-baseline first.")
        else:
            with open(baseline_path, "r", encoding="utf-8") as f:
                baseline = json.load(f)
            _print_comparison(baseline, metrics)


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the offline RAG eval.")
    parser.add_argument("--index", required=True, help="Chunk index name, e.g. miles_guo")
    parser.add_argument("--save-baseline", action="store_true", help="Save this run as baseline")
    parser.add_argument("--baseline", action="store_true", help="Compare against saved baseline")
    parser.add_argument("--concurrency", type=int, default=6, help="Parallel search/chat calls")
    args = parser.parse_args()
    asyncio.run(run(args.index, args.save_baseline, args.baseline, args.concurrency))


if __name__ == "__main__":
    main()
