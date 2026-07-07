# Plan: UK Parliament Hansard `chunk_index` (English, ~1M tokens)

## Motivation

Every current dataset (`miles_guo`, `lzj`, `lxb`, `mzd`) is Chinese-language
political content. For a UK audience — e.g. an interview demo — these corpora are
unreadable, lack shared context, and can read as politically sensitive.

**Hansard** is the official verbatim transcript of debates in the UK Parliament
(House of Commons / House of Lords). It is:

- **English** and instantly recognisable to a UK audience.
- **Politically neutral to present** — it is public-record civic data.
- **Structurally a near-twin of `miles_guo`**: a large, noisy corpus of many short
  speeches. The system's headline strengths (two-step retrieval, index-time document
  expansion, dedup, query expansion) transfer unchanged.

Goal: add a new `hansard` `chunk_index` **without touching the retrieval/agentic code** —
reuse the existing pipeline end-to-end.

## Scope / size target

Keep the footprint **well below** the existing `miles_guo` index — a small, cheap demo
tier. Reference numbers for `miles_guo` (see `docs/guides/data-preparation.md`): ~2,866
documents / ~48,751 chunks. We aim for roughly **a quarter of that**.

- **Target ≈ 1M tokens (~750k–800k words).** Do **not** ingest the full corpus
  (200+ years, billions of words).
- Concretely: **recent ~5–6 months of debates across 1–2 well-known topics** (e.g. cost
  of living + NHS). Small, but still real and noisy enough to show off two-step
  retrieval.
- Expected volume with the current chunker (`chunk_size=500`, `chunk_overlap=100`).
  Note `chunk_size`/`chunk_overlap` are **characters**, converted to tokens at index
  time ([chunker.py](../../lib/data/chunker.py)); for English (~4 chars/token) each
  chunk is only ~125 tokens (~90 words) with a ~100-token net advance:
  - ~1M tokens ≈ **~10k chunks** — roughly a quarter of `miles_guo`'s ~48k.
  - (English tokens *exceed* words, ~1.3×; the earlier "~1–2M tokens / 10k–20k chunks"
    estimate was inverted.)
  - Document granularity: **one debate section = one `doc_id`** (see below).
    ~300–600 debate documents is a healthy count for the title/summary layer.
- If the ~90-word chunks read too small in the demo, raise `chunk_size` for the Hansard
  path (see Chunker note) — this also *lowers* the chunk count further.
- Trivial for Elasticsearch Serverless; index build is a couple of minutes.

## Data source

- Official Hansard API / bulk data: <https://hansard.parliament.uk> (and
  <https://developer.parliament.uk>). Debates are addressable by house, date, and
  debate section, and are Crown-copyright / Open-Parliament-Licence — usable with
  attribution.
- Prefer the structured API (JSON per debate) over scraping HTML: it already gives us
  a debate title, date, and per-speech text with speaker names.

## How this maps onto the existing pipeline

The pipeline is dataset-agnostic; only the **downloader** and the per-dataset config
are new. Reused as-is:

| Stage | Existing component | Action for Hansard |
|---|---|---|
| Download | `lib/data/downloader_miles.py` (template) | **New** `lib/data/downloader_hansard.py` writing `data/data_hansard/documents/{doc_id}.txt` |
| Chunk | `lib/data/chunker.py` (`NaiveChunker`) | Reuse. Point `input_dir`/`output_dir` at `data_hansard`. Drop the `miles`-specific regex header/footer strip (or override via a Hansard-specific cleaner). |
| Titles | `lib/data/title_extractor.py` → `titles.json` | Reuse, **or** skip LLM extraction and use the debate title straight from the API (cheaper, already high quality). |
| Summaries | `lib/data/summary_extractor.py` → `summaries.json` | Reuse (LLM summary per debate). Optional but recommended — powers the two-step title/summary search. |
| Context | `lib/data/contexter.py` | Optional; can skip for v1 (like `lzj`/`lxb`). |
| Index chunks | `lib/search/elastic_chunk_index.py` (`ElasticWriteClientChunks`) | Reuse unchanged. Fields `text`, `doc_summary`, `doc_title`, `context` already match. |
| Index titles | `lib/search/elastic_title_index.py` | Reuse unchanged. |
| Register dataset | `lib/index_mapping.json` + `docs/README_INDEX.md` | **New** `hansard` entry, `doc_lang: "en"`. **Required** — see note below. |

> **Registration is a hard requirement, not a nicety.** `get_index_meta`
> ([lib/index_mapping.py](../../lib/index_mapping.py)) falls back for unregistered
> datasets to `doc_lang: "zh"`. An unregistered `hansard` would therefore run as
> *Chinese*, breaking query-language detection ([main.py:110-111](../../main.py#L110-L111))
> and degrading English retrieval. The `doc_lang: "en"` entry is what prevents this.

> **Why the retrieval layer needs no code change (the load-bearing assumption).**
> Retrieval is **BM25**, not vector embeddings — chunk search is a `multi_match`
> ([elastic_mix.py](../../lib/search/elastic_mix.py)) and title search a `multi_match`
> over `doc_summary^2` / `doc_title` ([elastic_title_index.py:215-227](../../lib/search/elastic_title_index.py#L215-L227)),
> so there is no Chinese-tuned embedding model to swap. The index mappings declare
> `text` fields with **no explicit analyzer** ([elastic_base.py:122-148](../../lib/search/elastic_base.py#L122-L148)),
> so Elasticsearch applies its default `standard` analyzer, which handles English
> natively (better, in fact, than it currently handles Chinese). `doc_lang: "en"` then
> only steers LLM prompt language and query expansion — not the analyzer. This is what
> makes "reuse the pipeline unchanged" hold.

### `doc_id` scheme

Chunk filenames are `{doc_id}_{chunk_id}.txt`. The indexer splits on the **last**
underscore (`rsplit("_", 1)`, [elastic_chunk_index.py:63](../../lib/search/elastic_chunk_index.py#L63)),
so `doc_id` may freely contain underscores — its content can never be mistaken for a
`chunk_id`. The only real constraint is that the chunker emit a **numeric** `chunk_id`
(it always does, [chunker.py:70-72](../../lib/data/chunker.py#L70-L72)), which
`neighbour_search` relies on.

- `doc_id` = stable Hansard debate identifier, e.g. `commons_2024-05-14_cost-of-living`.
  Avoid `.` in the `doc_id`: title extraction derives the id via `split(".")[0]`
  ([title_extractor.py:34](../../lib/data/title_extractor.py#L34)). Hyphenated dates are safe.
- `chunk_id` = sequential integer from the chunker (already the case).

## New code to write

1. `lib/data/downloader_hansard.py`
   - Iterate target (house, date-range, topic) tuples.
   - For each debate: fetch JSON, concatenate speeches as
     `"{Speaker}: {text}"` lines into one document, `re.sub(r'\s+', ' ', ...)` clean,
     write `data/data_hansard/documents/{doc_id}.txt`.
   - Also emit `data/data_hansard/titles.json` directly from the API to skip LLM title
     extraction (see **titles.json format** below).
   - Thread-pooled like the miles downloader; polite rate limiting.
2. `scripts/data_prepare_hansard.ipynb`
   - Copy the concrete template `scripts/data_prepare_miles.ipynb` (also `lxb`/`lzj`/`mzd`
     variants exist) and repoint it at `data_hansard`:
     download → chunk → (summary) → index chunks → index titles.
3. `lib/index_mapping.json` — add:
   ```json
   "hansard": { "title_index": "hansard_titles", "doc_lang": "en" }
   ```
4. `docs/README_INDEX.md` — add a bilingual catalog entry, e.g.:
   > `hansard`: UK Parliament (Hansard) debate transcripts, recent ~5–6 months across
   > 1–2 selected topics. Supports summary extraction; context expansion optional.

## titles.json format

Hand-writing `titles.json` from the API is drop-in — it just has to match what
`TitleExtractor.run` would have produced ([title_extractor.py:68-70](../../lib/data/title_extractor.py#L68-L70)):
a **flat JSON object** mapping `doc_id → title`, no nesting:

```json
{
  "commons_2024-05-14_cost-of-living": "Cost of Living",
  "commons_2024-05-21_nhs-waiting-times": "NHS Waiting Times"
}
```

Rules that make it index cleanly via `ElasticWriteClientTitles.insert_titles`
([elastic_title_index.py:114-158](../../lib/search/elastic_title_index.py#L114-L158)):

- **Keys must be the exact `doc_id`** — i.e. the document filename stem without `.txt`
  (`data/data_hansard/documents/{doc_id}.txt`), the same `doc_id` the chunker derives.
  Mismatched keys don't error; `insert_titles` silently falls back to `""` via
  `self.titles.get(doc_id, "")`, so a title simply goes missing. Generate both the
  `.txt` filename and the `titles.json` key from one source string to keep them in lockstep.
- **Every document needs an entry** — the title index is populated by iterating
  `titles.json` (or `summaries.json`); a document absent from both is never indexed in
  the title layer and won't surface in two-step retrieval.
- **Summaries follow the identical shape** — if you run the LLM summary extractor it
  emits the same `{doc_id: summary}` dict to `summaries.json`; pass both `title_path`
  and `summaries_path` to index them together.

## Chunker note

`NaiveChunker.load_data_to_paragraphs` currently strips `miles`-specific header/footer
markers (`内容梗概:`, the Gnews footer) and assumes Chinese chars-per-token. For English:

- Remove/skip those regexes for the Hansard path.
- The tiktoken `cl100k_base` chars-per-token estimate self-calibrates from a sample, so
  English (~4 chars/token) is handled automatically — no hard-coded change needed, but
  verify chunk sizes on a sample.

Cleanest approach: add a `header_footer_strip=None` (or a `cleaner` callable) parameter
to `NaiveChunker` rather than branching on dataset name, keeping the miles behaviour as
the default.

## Demo script (interview)

Select `chunk_index = hansard`, then ask questions a UK interviewer immediately gets:

- "What has been said in Parliament about the cost of living crisis this past year?"
- "Summarise the main arguments made about NHS waiting times."
- "Which concerns were raised about energy prices, and by whom?"

The agentic pipeline first locates relevant debates via title/summary search, then
retrieves specific speeches, and returns a cited answer — the same value proposition as
the `miles_guo` demo, but legible to the audience.

## Acceptance criteria

- [ ] `data/data_hansard/documents/` populated; total ≈ 1M tokens (~750k–800k words,
      ~10k chunks).
- [ ] Chunk sizes verified on a real Hansard sample — confirm the tiktoken
      chars-per-token self-calibration ([chunker.py:95-98](../../lib/data/chunker.py#L95-L98))
      yields the expected ~125-token chunks for English before the full build, and raise
      `chunk_size` if the ~90-word chunks read too small.
- [ ] Chunks + titles (+ optional summaries) indexed into `hansard` / `hansard_titles`.
- [ ] `hansard` registered in `lib/index_mapping.json` and `docs/README_INDEX.md`.
- [ ] Frontend works with `hansard` **with no frontend code change**: the `chunk_index`
      field is a free-text input ([frontend/src/rag.ts:729](../../frontend/src/rag.ts#L729),
      [agentic.ts:870](../../frontend/src/agentic.ts#L870)), so typing `hansard` or passing
      `?chunk_index=hansard` is sufficient. (A real dataset *picker* is separate, optional
      scope.) The three demo questions above return sensible, cited answers.
- [ ] No changes required in `lib/agentic/`, `lib/rag/`, `lib/skills/`, or
      `lib/search/elastic_*` beyond the new dataset registration.

## Out of scope

- Full historical Hansard ingest.
- Speaker-level filtering / structured metadata search (possible follow-up: add a
  `speaker` field to `ElasticChunk`).
- Context-expansion (`contexter.py`) — deferrable to a later iteration.
