"""Generate an offline RAG eval question set from indexed chunks.

Samples chunks from Elasticsearch, asks an LLM to write one question answerable
only from each chunk, and writes the questions (with their source chunk as the
retrieval ground truth) to ``test/eval_data/<index>.jsonl``.

See ``docs/plan/metrics.md`` for the design.

Usage:
    poetry run python -m lib.eval.dataset_gen --index miles_guo --n 200 --seed 42
"""

import argparse
import asyncio
import json
import random
from pathlib import Path

from lib.search.elastic_chunk_index import ElasticReadClientChunks
from lib.llm.litellm_api import call_llm_with_fallback
from lib.app_logger import get_logger

logger = get_logger(__name__)

# Repo-root-relative directory for committed eval data.
EVAL_DATA_DIR = Path(__file__).resolve().parents[2] / "test" / "eval_data"

# Skip chunks shorter than this (too little to form a real question).
MIN_CHUNK_LEN = 120
# Skip chunks longer than this when prompting (keep the LLM call cheap).
MAX_CHUNK_PROMPT_LEN = 2000
# At most this many questions per source document, to spread coverage.
MAX_PER_DOC = 2

_QUESTION_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "eval_question",
        "schema": {
            "type": "object",
            "properties": {
                "q": {"type": "string"},
                "gold": {"type": "string"},
            },
            "required": ["q", "gold"],
            "additionalProperties": False,
        },
    },
}


def _is_garbage(text: str) -> bool:
    """Heuristic reject: empty, too short, or mostly non-word characters."""
    if not text or len(text.strip()) < MIN_CHUNK_LEN:
        return True
    stripped = text.strip()
    # Reject chunks that are mostly punctuation / symbols (e.g. tables of dashes).
    word_chars = sum(1 for c in stripped if c.isalnum())
    if word_chars / max(len(stripped), 1) < 0.5:
        return True
    return False


async def _scan_chunks(index: str) -> list[dict]:
    """Read every chunk from the index, returning dicts with doc_id/chunk_id/text."""
    client = ElasticReadClientChunks()
    chunks: list[dict] = []
    try:
        async for hit in client.helpers.async_scan(
            client.async_client,
            index=index,
            query={"query": {"match_all": {}}},
            _source=["doc_id", "chunk_id", "text"],
        ):
            src = hit.get("_source", {})
            chunks.append(
                {
                    "doc_id": src.get("doc_id", ""),
                    "chunk_id": src.get("chunk_id", ""),
                    "text": src.get("text", ""),
                }
            )
    finally:
        await client.async_client.close()
    return chunks


def _sample(chunks: list[dict], n: int, seed: int) -> list[dict]:
    """Deterministically pick up to ``n`` non-garbage chunks, <= MAX_PER_DOC each."""
    usable = [c for c in chunks if not _is_garbage(c["text"])]
    rng = random.Random(seed)
    rng.shuffle(usable)

    per_doc: dict[str, int] = {}
    picked: list[dict] = []
    for chunk in usable:
        if per_doc.get(chunk["doc_id"], 0) >= MAX_PER_DOC:
            continue
        picked.append(chunk)
        per_doc[chunk["doc_id"]] = per_doc.get(chunk["doc_id"], 0) + 1
        if len(picked) >= n:
            break
    return picked


async def _generate_question(chunk: dict) -> dict | None:
    """Ask the LLM for one question + gold answer grounded in this chunk."""
    passage = chunk["text"].strip()[:MAX_CHUNK_PROMPT_LEN]
    prompt = (
        "Here is a passage:\n"
        f"\"\"\"\n{passage}\n\"\"\"\n\n"
        "Write one question that can be answered ONLY from this passage, and give "
        "its answer. The question must be specific and self-contained (do not say "
        "'according to the passage'). Answer in the same language as the passage. "
        'Return JSON: {"q": "<question>", "gold": "<answer>"}.'
    )
    try:
        result = await call_llm_with_fallback(
            prompt, model_name="gpt", response_format=_QUESTION_SCHEMA
        )
        if isinstance(result, str):
            result = json.loads(result)
        q = (result.get("q") or "").strip()
        gold = (result.get("gold") or "").strip()
        if not q or not gold:
            return None
        return {"q": q, "gold": gold}
    except Exception as e:
        logger.warning("Question generation failed for %s_%s: %s",
                       chunk["doc_id"], chunk["chunk_id"], e)
        return None


async def build_dataset(index: str, n: int, seed: int, concurrency: int = 8) -> Path:
    logger.info("Scanning chunks from index '%s'...", index)
    chunks = await _scan_chunks(index)
    logger.info("Read %d chunks; sampling %d (seed=%d)...", len(chunks), n, seed)
    sampled = _sample(chunks, n, seed)
    if not sampled:
        raise SystemExit(f"No usable chunks found in index '{index}'.")

    sem = asyncio.Semaphore(concurrency)

    async def _one(i: int, chunk: dict) -> dict | None:
        async with sem:
            gen = await _generate_question(chunk)
        if gen is None:
            return None
        return {
            "id": f"{index}_{i:04d}",
            "q": gen["q"],
            "gold": gen["gold"],
            "doc_id": chunk["doc_id"],
            "chunk_id": chunk["chunk_id"],
        }

    tasks = [_one(i, c) for i, c in enumerate(sampled)]
    rows = [r for r in await asyncio.gather(*tasks) if r is not None]

    EVAL_DATA_DIR.mkdir(parents=True, exist_ok=True)
    out_path = EVAL_DATA_DIR / f"{index}.jsonl"
    with open(out_path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")

    logger.info("Wrote %d questions to %s", len(rows), out_path)
    print(f"Wrote {len(rows)} questions to {out_path}")
    return out_path


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a RAG eval question set.")
    parser.add_argument("--index", required=True, help="Chunk index name, e.g. miles_guo")
    parser.add_argument("--n", type=int, default=200, help="Number of questions to sample")
    parser.add_argument("--seed", type=int, default=42, help="Sampling seed for reproducibility")
    parser.add_argument("--concurrency", type=int, default=8, help="Parallel LLM calls")
    args = parser.parse_args()
    asyncio.run(build_dataset(args.index, args.n, args.seed, args.concurrency))


if __name__ == "__main__":
    main()
