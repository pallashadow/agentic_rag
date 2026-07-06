# Plan: UK Parliament Hansard `chunk_index` (English, ~3–5M words)

## Motivation

Every current dataset (`miles_guo`, `lzj`, `lxb`, `mzd`, `epstein9`) is Chinese-language
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

- **~3–5M words** ≈ a "comfortable demo" tier. Do **not** ingest the full corpus
  (200+ years, billions of words).
- Concretely: **recent ~2 years of debates across a handful of well-known topics**
  (e.g. cost of living, NHS, Brexit/EU relations, energy). This keeps the corpus real
  and noisy enough to show off two-step retrieval while ingest stays minutes-scale.
- Expected volume with the current chunker (`chunk_size=500`, `chunk_overlap=100`):
  - 3–5M words ≈ **~1–2M tokens** ≈ **~10k–20k chunks**.
  - Document granularity: **one debate section = one `doc_id`** (see below).
    ~500–2000 debate documents is a healthy count for the title/summary layer.
- Trivial for Elasticsearch Serverless; index build is minutes, not hours.

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
| Register dataset | `lib/index_mapping.json` + `docs/README_INDEX.md` | **New** `hansard` entry, `doc_lang: "en"`. |

### `doc_id` scheme

Chunk filenames must be `{doc_id}_{chunk_id}.txt` and `doc_id` may contain underscores
(the indexer uses `rsplit("_", 1)`), but `chunk_id` must stay **numeric** so
`neighbour_search` works. Recommended:

- `doc_id` = stable Hansard debate identifier, e.g. `commons_2024-05-14_cost-of-living`
  (avoid trailing numeric-only segments that could be confused with a chunk_id — keep a
  non-numeric tail).
- `chunk_id` = sequential integer from the chunker (already the case).

## New code to write

1. `lib/data/downloader_hansard.py`
   - Iterate target (house, date-range, topic) tuples.
   - For each debate: fetch JSON, concatenate speeches as
     `"{Speaker}: {text}"` lines into one document, `re.sub(r'\s+', ' ', ...)` clean,
     write `data/data_hansard/documents/{doc_id}.txt`.
   - Also emit `data/data_hansard/titles.json` (`{doc_id: debate_title}`) directly from
     the API to skip LLM title extraction.
   - Thread-pooled like the miles downloader; polite rate limiting.
2. `scripts/data_prepare_hansard.ipynb`
   - Mirror the existing `data_prepare_*` flow referenced in `docs/guides/data-preparation.md`:
     download → chunk → (summary) → index chunks → index titles.
3. `lib/index_mapping.json` — add:
   ```json
   "hansard": { "title_index": "hansard_titles", "doc_lang": "en" }
   ```
4. `docs/README_INDEX.md` — add a bilingual catalog entry, e.g.:
   > `hansard`: UK Parliament (Hansard) debate transcripts, recent ~2 years across
   > selected topics. Supports summary extraction; context expansion optional.

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

- "What has been said in Parliament about the cost of living crisis since 2022?"
- "Summarise the main arguments made about NHS waiting times."
- "Which concerns were raised about energy prices, and by whom?"

The agentic pipeline first locates relevant debates via title/summary search, then
retrieves specific speeches, and returns a cited answer — the same value proposition as
the `miles_guo` demo, but legible to the audience.

## Acceptance criteria

- [ ] `data/data_hansard/documents/` populated; total ≈ 3–5M words.
- [ ] Chunks + titles (+ optional summaries) indexed into `hansard` / `hansard_titles`.
- [ ] `hansard` registered in `lib/index_mapping.json` and `docs/README_INDEX.md`.
- [ ] Frontend dataset dropdown offers `hansard`; the three demo questions above return
      sensible, cited answers.
- [ ] No changes required in `lib/agentic/`, `lib/rag/`, `lib/skills/`, or
      `lib/search/elastic_*` beyond the new dataset registration.

## Out of scope

- Full historical Hansard ingest.
- Speaker-level filtering / structured metadata search (possible follow-up: add a
  `speaker` field to `ElasticChunk`).
- Context-expansion (`contexter.py`) — deferrable to a later iteration.
