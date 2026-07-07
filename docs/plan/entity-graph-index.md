# Plan: Vector-free LightRAG-style **local + global** retrieval for `miles_guo`

## Motivation

The current retrieval is BM25-only and **chunk-centric**: `general_search` does a
`multi_match` over `text^2 / doc_summary / context`
([elastic_chunk_index.py:373-382](../../lib/search/elastic_chunk_index.py#L373-L382))
plus the two-step title→chunk pass ([elastic_mix.py:67-90](../../lib/search/elastic_mix.py#L67-L90)).
This is deliberately vector-free (see the design rationale in
[rag-system.md:84-119](../architecture/rag-system.md#L84-L119)) and works well for
"find the chunk that lexically matches the query". It has three structural blind spots
that LightRAG is built to remove:

1. **Alias / coreference misses.** A chunk that writes 「郭先生」 or "Miles Kwok" is not
   retrieved by a query for 「郭文贵」. BM25 matches surface strings; it has no notion
   that these denote the same entity.
2. **No cross-document aggregation.** Two-step retrieval is confined *within* the
   documents surfaced by title search. Questions whose evidence is scattered across
   many documents and only connected through a shared entity ("综述郭文贵与法治基金",
   "X 是谁") cannot assemble that evidence — the relevant chunks live in different
   `doc_id`s that no single title/summary surfaces together.
3. **No relation-level matching.** A question that is *about a relationship*
   ("谁资助了班农参与的项目", "郭文贵和法治基金是什么关系") expresses an abstract
   relation, not a chunk-local surface string. BM25 over chunks cannot route to the
   documents that jointly witness that relation unless the exact phrasing happens to
   appear together.

**This plan implements LightRAG's dual retrieval — both `local` (entity) and `global`
(relation) — without any encoder.** LightRAG (HKU) extracts entities *and relations* per
chunk, then at query time matches low-level query keywords to entities (`local`) and
high-level query keywords to relations (`global`), gathers the graph neighbourhood, and
selects the associated source chunks. The only thing we change is the *matching
substrate*: LightRAG matches with **dense vectors**; we match with **index-time
canonicalization + query-time exact/BM25 lookup**. We keep the graph, both retrieval
modes, and the provenance model.

Goal: add a **LightRAG-style entity + relation layer** to `miles_guo` that

- extracts entities and relations (with keywords) per chunk;
- merges same-name records and, beyond LightRAG's indexing, runs an automatic, auditable
  **alias canonicalization** stage;
- builds an **entity index** (`local`) and a **relation index** (`global`), plus a graph
  adjacency for one-hop expansion;
- retrieves via `local` (entity) **and** `global` (relation) paths, expands one hop, and
  collects entity-source and relation-source chunks as separate ranked channels;
- **cites** only original `miles_guo` chunks as answer evidence; entity `profile` and
  relation `description` may enter the answer LLM's context to aid generation, but are never
  emitted as `DocumentResult`s and never become citable sources.

The chunk index `miles_guo` is **not rebuilt or modified**. Entities and relations are
**indexes of pointers back into the existing chunk index**, not new answer sources.

## LightRAG baseline and our deliberate divergence

This design implements LightRAG's structure. The distinction from the original is narrow
and must remain explicit:

1. **Original LightRAG indexing.** Extracts entities and relations per chunk, merges
   records sharing the same `entity_name`, aggregates their descriptions (LLM summary
   when needed), and retains source chunk IDs. Entity vector content is the entity name
   plus its aggregated description; **relation vector content includes relation keywords,
   endpoint names, and its aggregated description.**
2. **Original LightRAG retrieval.** An LLM extracts low-level and high-level query
   keywords. Vector search maps low-level keywords to entities (`local`) and high-level
   keywords to relations (`global`), after which graph neighbourhoods and associated
   source chunks are gathered.
3. **Original LightRAG answer context.** Entity descriptions, relation descriptions, and
   original chunks are all supplied to the answer LLM.
4. **Our divergences (three, all narrow).**
   - **(a) Vector-free matching.** We replace both the entity vector match and the
     relation vector match with exact/BM25 lookup. Entity content is matched over
     `canonical_name / aliases / aliases_normalized / profile`; relation content is
     matched over `endpoint names / relation keywords / relation description`. **We keep
     `global`; we replace only its encoder.** This is a known, bounded weakening — BM25
     cannot match abstract relation semantics ("资助"↔"提供资金") on surface form the way
     a dense vector can. Section [Evaluation](#phase-e--evaluation) measures it.
   - **(b) Automatic alias canonicalization.** LightRAG provides a manual
     `merge_entities(...)` management API that rewires relationships and merges
     source-chunk tracking, but its *indexing* path only merges by exact extracted
     entity name; it does not auto-discover aliases such as 「郭文贵」/「郭先生」/"Miles
     Kwok". We add an auditable canonicalization stage before indexing.
   - **(c) Chunks-only citation.** LightRAG feeds entity and relation descriptions into
     the answer context. Our existing citation contract requires that only original
     chunks are quotable evidence. So entity **profiles** and relation **descriptions**
     are used only to *retrieve and rank* chunks; they are never emitted as a
     `DocumentResult` and never cited. Graph descriptions route retrieval; original
     chunks are the answer.

Primary references: the official
[LightRAG paper](https://aclanthology.org/2025.findings-emnlp.568.pdf) and the official
repository at pinned commit
[`e9ddb8d`](https://github.com/HKUDS/LightRAG/tree/e9ddb8d46c55d3138663e7d0a4ca5ca2c05d4641):
[`operate.py`](https://github.com/HKUDS/LightRAG/blob/e9ddb8d46c55d3138663e7d0a4ca5ca2c05d4641/lightrag/operate.py),
[`prompt.py`](https://github.com/HKUDS/LightRAG/blob/e9ddb8d46c55d3138663e7d0a4ca5ca2c05d4641/lightrag/prompt.py),
[`pipeline.py`](https://github.com/HKUDS/LightRAG/blob/e9ddb8d46c55d3138663e7d0a4ca5ca2c05d4641/lightrag/pipeline.py),
[`lightrag.py`](https://github.com/HKUDS/LightRAG/blob/e9ddb8d46c55d3138663e7d0a4ca5ca2c05d4641/lightrag/lightrag.py), and
[`utils_graph.py`](https://github.com/HKUDS/LightRAG/blob/e9ddb8d46c55d3138663e7d0a4ca5ca2c05d4641/lightrag/utils_graph.py).

> **Version note.** Line references above are to pinned commit `e9ddb8d`. The working
> reference checkout (`D:\PROJECT\LightRAG_ref`) is **v1.5.5**, whose retrieval was
> refactored into a 4-stage `_build_query_context` (search → token-truncate → merge chunks →
> build context, `operate.py:5032`). The mechanisms this plan conforms to — occurrence-count
> weighted chunk polling (`pick_by_weighted_polling`, `utils.py:3991`), the single
> naive/entity/relation round-robin merge (`_merge_all_chunks`, `operate.py:4739`), relation
> channel dedup against the entity channel (`_find_related_text_unit_from_relations`,
> `operate.py:5519`), and query-time token truncation (`_apply_token_truncation`,
> `operate.py:4533`) — are the **v1.5.5** shapes and are what governs where this plan
> diverges. Whenever the pinned-commit description and v1.5.5 differ, this plan follows
> **v1.5.5**.

### LightRAG data lifecycle, and what this plan does differently

This plan borrows LightRAG's provenance model, but not its complete online storage
lifecycle. The distinction is based on the current implementation, not inferred from the
paper alone:

1. **Incremental enqueue and resume in LightRAG.** `apipeline_enqueue_documents()`
   assigns or accepts document IDs, deduplicates, and persists document status so the
   processing loop can resume pending/failed/interrupted documents rather than treating the
   graph as a one-shot artifact
   ([pipeline.py:232](https://github.com/HKUDS/LightRAG/blob/e9ddb8d46c55d3138663e7d0a4ca5ca2c05d4641/lightrag/pipeline.py#L232)).
2. **Source tracking and document deletion in LightRAG.** In addition to graph `source_id`,
   LightRAG maintains entity/relation→chunk tracking. `adelete_by_doc_id()` subtracts the
   deleted document's chunks, deletes entities/relations with no remaining source, and
   rebuilds shared items from the remaining chunks
   ([lightrag.py:3111](https://github.com/HKUDS/LightRAG/blob/e9ddb8d46c55d3138663e7d0a4ca5ca2c05d4641/lightrag/lightrag.py#L3111)).
3. **Entity merge in current LightRAG.** `amerge_entities(...)` is an explicit management
   operation that merges descriptions and source IDs, redirects and deduplicates
   relationships, merges chunk tracking, and removes source entities
   ([utils_graph.py:1708](https://github.com/HKUDS/LightRAG/blob/e9ddb8d46c55d3138663e7d0a4ca5ca2c05d4641/lightrag/utils_graph.py#L1708),
   impl at
   [utils_graph.py:1216](https://github.com/HKUDS/LightRAG/blob/e9ddb8d46c55d3138663e7d0a4ca5ca2c05d4641/lightrag/utils_graph.py#L1216)).
   It is not automatic alias discovery; callers must already know which entities to merge.
4. **One-hop retrieval and chunk selection in current LightRAG (v1.5.5).** After matching
   entities (`local`, `_get_node_data`, `operate.py:5152`) and relations (`global`,
   `_get_edge_data`, `operate.py:5427`), LightRAG picks source chunks **per entity and per
   relation by occurrence-count weighted polling** — its vector-free `WEIGHT` method
   (`pick_by_weighted_polling`, `utils.py:3991`; default `related_chunk_number=5`,
   `min_related_chunks=1`). Chunks are sorted by how many entities/relations cite them and
   allocated with a linear-decreasing quota; there is **no BM25 or lexical re-rank** in this
   path. `VECTOR` is only the *other* configurable method and is the one thing we drop. The
   **relation channel is deduped against the already-selected entity chunks before it is
   ranked** (`_find_related_text_unit_from_relations`, `operate.py:5519`), so it contributes
   only *new* chunks; this dedup-before-rank is load-bearing — collapsing the channels first
   would make the relation/`global` channel a no-op. LightRAG then **round-robin merges three
   channels — naive (vector) chunks, entity chunks, relation chunks — with a single dedup by
   chunk id** (`_merge_all_chunks`, `operate.py:4739`, round-robin body at `operate.py:4785`),
   recording per-chunk `source/frequency/order` tracking. Phase C conforms: occurrence-count
   weighted polling for within-channel selection (not BM25), relation channel deduped against
   the entity channel before selection, and a single round-robin over the naive
   (`general_search`) / entity / relation channels.
5. **Our v1 lifecycle.** This feature is an offline, full-build index for one fixed
   `miles_guo` chunk snapshot. It borrows source-chunk tracking and deterministic merge
   output, but does **not** implement LightRAG's online document queue, document-status
   state machine, per-document delete/rebuild API, graph/vector dual-write, or manual
   graph-management API. If the chunk snapshot, extraction prompt/schema, glossary, or
   extraction model changes, the supported operation is to regenerate
   `entities_raw.jsonl`, rerun the global resolver, and recreate `miles_guo_entities`
   **and** `miles_guo_relations`; mixing records from different builds is forbidden.
   Online incremental maintenance is a separate follow-up.

| Concern | Current LightRAG | This plan |
|---|---|---|
| Entity merge during indexing | Automatically aggregates records with the same extracted entity name | Same-name aggregation plus automatic alias candidate generation and audited canonicalization |
| Known aliases after indexing | Explicit caller-driven `merge_entities(...)` | Resolver produces canonical clusters before indexing; no query-time graph mutation |
| Provenance | Graph `source_id` plus entity/relation chunk-tracking stores | `source_chunks[]` on entities **and** on relations in the immutable build artifact |
| One-hop chunk selection | Occurrence-count weighted polling (`WEIGHT`) per entity/relation; relation channel deduped against entity channel; single round-robin over naive/entity/relation channels | **Same method** — occurrence-count weighted polling per entity/relation (LightRAG's vector-free `WEIGHT`, no BM25 re-rank); relation channel deduped against entity channel before selection; single round-robin over naive (`general_search`)/entity/relation channels |
| Incremental documents | Document queue, content/filename dedup, status state machine, retry/resume | Not supported in v1; resume is only within one matching offline build manifest |
| Delete/update one document | Subtract deleted chunk IDs; delete orphan graph items; rebuild shared items | Not supported in v1; any corpus/config change triggers a complete rebuild of both artifacts and both indices |
| Storage | KV + graph + vector stores; graph authoritative, vectors rebuildable | Two Elasticsearch routing indices (`_entities`, `_relations`); the chunk index remains the sole answer-evidence store |
| Retrieval | `local` entity + `global` relation keywords matched through **dense vectors** | `local` entity + `global` relation, matched through **exact/BM25** over names, aliases, relation keywords, and descriptions |
| Answer context | Entity descriptions, relation descriptions, and source chunks | Only original source chunks enter `DocumentResult[]`; profiles and relation descriptions only route retrieval |

Before this feature ships, the full provenance and decision history above must be moved
from this planning document into a formal architecture document at
`docs/architecture/entity-graph-retrieval.md`. That document must explain the original
LightRAG flow, every deliberate deviation, the evidence-traceability rationale, known
losses, and evaluation results. `docs/architecture/rag-system.md` and `docs/README.md`
must link to it; the plan alone is not the permanent design record.

## What we borrow from LightRAG, and what we drop

| LightRAG component | Decision | Our form |
|---|---|---|
| LLM entity + relation extraction per **chunk** | **Keep** | new `lib/data/entity_extractor.py` — entities **and relations with keywords** |
| Cross-chunk **same-name merge** ([merge_nodes_and_edges, operate.py:2922](https://github.com/HKUDS/LightRAG/blob/e9ddb8d46c55d3138663e7d0a4ca5ca2c05d4641/lightrag/operate.py#L2922)) | **Keep** | aggregate descriptions and source chunks per resolved entity |
| Cross-alias **canonicalization** | **Add automatic indexing stage beyond LightRAG (load-bearing)** | discovers bounded candidates, emits canonical name + `aliases[]` + audit report |
| Entity/relation → **source chunks** K-V map | **Keep** | entity `source_chunks[]`; each relation retains its own `source_chunks[]` |
| Per-entity **profile** (summarized description) | **Keep for retrieval only** | `profile` field; never emitted as answer evidence |
| Per-relation **description + keywords** | **Keep for retrieval only** | relation index content; never emitted as answer evidence |
| One-hop **neighbour** gathering (main flow) | **Keep** | graph adjacency; entity↔relation one-hop expansion is standard, not a refine-only fallback |
| `local`: query keyword → **entity** match via **dense vector** | **Keep, replace substrate** | entry_llm extracts local keywords / entity mentions → exact `terms` on `aliases_normalized` + BM25 over `canonical_name / aliases / profile` |
| `global`: query keyword → **relation** match via **dense vector** | **Keep, replace substrate** | entry_llm extracts global keywords → BM25 over relation `description / keywords / endpoint names` + exact endpoint `terms` |
| Dense vector DB (nano-vectordb) | **Drop** | stays pure Elasticsearch |
| Entity/relation descriptions in **answer context** | **Drop** | only original chunks are citable; descriptions route retrieval only |

> **What the vector-free `global` gives up.** Dense `global` matches *abstract relation
> semantics* ("资助"↔"提供资金", "对立"↔"反对") that BM25 cannot match on surface form. Our
> BM25/exact relation retriever recovers the *structural* benefit of `global` (routing to
> the documents that jointly witness a relation, and to relations whose endpoints or
> keywords are named in the query) but not full semantic paraphrase matching. This is a
> **known, bounded loss**: `global` can miss when the query paraphrases a relation with no
> shared surface token, when relation extraction misses an edge, or when the relevant
> relation falls outside the per-entity edge cap. Phase E quantifies it, and a material
> `global` regression triggers a follow-up (a learned or expanded keyword layer), not a
> silent drop of the mode.

## Architecture: local + global retrieval into the shared chunk index

Add a fourth skill next to `general_search` / `document_search` / `neighbour_search`
([factory.py:22-26](../../lib/skills/factory.py#L22-L26)). `lightrag_search` returns the
same `DocumentResult` shape (`doc_id, chunk_id, text, doc_title, score, index`,
[general_search.py:26-33](../../lib/skills/general_search.py#L26-L33)); the entity/relation
layer is an **index of pointers back into the existing chunk index**, not a new answer
source.

The existing execution node concatenates skill results without cross-skill de-duplication
([rag_search_node.py:95-161](../../lib/agentic/nodes/rag_search_node.py#L95-L161)). This
feature adds **one** shared merge, called once after all planned skills, that directly
mirrors LightRAG's `_merge_all_chunks`
(`operate.py:4739`, round-robin body at
[operate.py:4785](https://github.com/HKUDS/LightRAG/blob/e9ddb8d46c55d3138663e7d0a4ca5ca2c05d4641/lightrag/operate.py#L4785),
where it round-robin-merges the **naive / entity / relation** chunk channels and dedups by
chunk id). Following LightRAG, the merge is **single-level over exactly three co-equal
channels** — there is no intra-skill pre-merge that collapses entity and relation before
they meet the naive channel:

1. the three channels are: `general_search`'s ordered chunks (the **naive** channel,
   playing the role of LightRAG's vector chunks), and `lightrag_search`'s **entity-source**
   and **relation-source** channels. `lightrag_search` therefore returns its two channels
   *separately* (it does not pre-fuse them into one `DocumentResult[]`); the shared merge is
   the sole round-robin;
2. round-robin across the three channels in LightRAG's order — naive, then entity, then
   relation at each rank i — appending a hit only if its `(doc_id, chunk_id)` was not already
   taken. Raw Elasticsearch scores are never compared across channels; only per-channel rank
   order is used;
3. reassign `index` from 1 in merged order (the existing frontend reads `index`/order, so
   no per-skill score normalization is introduced);
4. cap the merged set to `search_config.chunk_k`, so adding a skill cannot silently double
   the answer-context budget.

This reuses the project's existing dedup contract (dedup by `(doc_id, chunk_id)`, keep
first, re-index — [postprocess_search_results](../../lib/search/elastic_mix.py#L175-L233))
and adds only the round-robin interleave that LightRAG uses to keep each channel
represented. No reciprocal-rank fusion or any other invented scoring is introduced.

```
query
  └─ entry_llm ──► classifies + extracts local_keywords, global_keywords, entity_mentions
        ├─ general_search  (existing: BM25 chunk + two-step)          ── LightRAG "naive"  ┐
        └─ lightrag_search (NEW)                                                            │
              local  path: entity_mentions / local_keywords ─► miles_guo_entities          │
              global path: global_keywords / query          ─► miles_guo_relations         │  three
              expand: matched entities → adjacent relations                                │  co-equal
                      matched relations → endpoint entities                                │  channels
              select chunks per entity/relation by occurrence-count weighted polling       │
                      (LightRAG WEIGHT; relation channel deduped vs entity channel first)  │
              emit TWO ordered channels (NOT pre-fused):                                   │
                        entity-source chunk ids   ─────────────────────────────────────────┤
                        relation-source chunk ids ─────────────────────────────────────────┘
        ▼
   single round-robin merge(naive, entity, relation) + dedup by (doc_id,chunk_id)
     + per-doc cap + global chunk_k  → fetch miles_guo chunks → DocumentResult[]
     → rag_reply → validation (may loop)
```

The entity and relation indices are routing structures, not answer sources. `profile` and
relation `description` may influence which entities, relations, and source chunks are
selected, but must not be converted into synthetic `DocumentResult`s; this preserves the
existing citation contract.

---

## Phase A — Data preparation (offline, one-time)

Both steps mirror the existing async + `call_llm_with_fallback` pattern of
[summary_extractor.py](../../lib/data/summary_extractor.py). JSONL output uses a single
writer queue and atomic checkpoints; workers must not append concurrently to the same
file. A build manifest records the chunk/context snapshot hash, extraction prompt and
schema hashes, glossary hash, and actual extraction model. `skip_existing` is valid only
when that manifest exactly matches the running build. A mismatch fails closed and requires
a fresh `entities_raw.jsonl`.

### A1. Chunk-level extraction — `lib/data/entity_extractor.py`

- **Input:** existing chunk files `data/data_miles/chunks/{doc_id}_{chunk_id}.txt` plus
  the matching `contexts/{doc_id}_{chunk_id}.txt` ([contexter.py](../../lib/data/contexter.py)
  output). Delimit them as `TARGET_CHUNK` and `DISAMBIGUATION_CONTEXT`: context may resolve
  a pronoun or abbreviated mention, but every extracted entity/relation needs an evidence
  span in `TARGET_CHUNK`.
- **Prompt:** ask for
  - **entities** (`mention_text, resolved_name, type, mention_kind, description,
    evidence_span, confidence`); `mention_kind ∈ {proper_name, alias, title, pronoun}`.
  - **relations** (`src, tgt, description, keywords, evidence_span, confidence`).
    `keywords` is a short list of high-level relation terms mirroring LightRAG's
    `relationship_keywords`
    ([prompt.py:71-84](https://github.com/HKUDS/LightRAG/blob/e9ddb8d46c55d3138663e7d0a4ca5ca2c05d4641/lightrag/prompt.py#L71-L84))
    — e.g. `["资助","发起"]` — and is the **content the vector-free `global` retriever matches
    on**. Without it, `global` degrades to endpoint-name matching only.
  - **Seed a domain glossary** of known entities/aliases (郭文贵/郭先生/Miles Kwok,
    法治基金/Rule of Law Foundation, 班农/Steve Bannon…) in versioned
    `data/data_miles/entity_glossary.json` with `canonical_name`, `type`, `aliases`, and
    optional `cannot_links`; record its content hash in extraction and merge reports.
- **Validation:** reject records whose evidence span is absent from `TARGET_CHUNK`, whose
  relation endpoint is absent from that record's entity list, or whose confidence is below
  `0.7`. Pronouns remain valid provenance-bearing mentions but must never become queryable
  aliases.
- **Output:** `data/data_miles/entities_raw.jsonl`, one line per chunk:
  ```json
  {"doc_id":"...","chunk_id":"3",
   "entities":[{"mention_text":"郭先生","resolved_name":"郭文贵","type":"person",
                "mention_kind":"title","description":"...","evidence_span":"郭先生表示…",
                "confidence":0.96}],
   "relations":[{"src":"郭文贵","tgt":"法治基金","description":"发起并资助",
                 "keywords":["发起","资助"],"evidence_span":"…发起法治基金…",
                 "confidence":0.91}]}
  ```
- Async with `asyncio.Semaphore(max_workers)`. Within a matching build manifest,
  `skip_existing` is keyed on `doc_id_chunk_id` and skips only validated completed records.

### A2. Global canonicalization + profile + relation aggregation — `lib/data/entity_resolver.py`

A **global pass** (cannot be done per-chunk). Reads `entities_raw.jsonl`, produces
`data/data_miles/entities.json` **and** `data/data_miles/relations.json`:

1. **Normalize.** One shared function at index and query time: Unicode NFKC, `casefold()`,
   trim/collapse whitespace, normalize common punctuation. Do **not** blindly strip
   honorifics: generic forms such as 「先生」 are ambiguous.
2. **Canonicalize (extension beyond LightRAG).** Apply exact normalized-name and explicit
   seed-glossary mappings first. For residual names, generate bounded candidates within the
   same entity type using normalized string similarity and shared source context, then ask
   the LLM for pairwise `same / different / uncertain` decisions with supporting mentions.
   Merge only `same` decisions with confidence `>= 0.9`; keep `uncertain` separate. Reject
   any union that violates a seed cannot-link and record it in the audit. Choose the
   canonical representative deterministically: explicit seed canonical name first, then
   highest mention count, then normalized lexical order. Never send an unbounded
   entity-type bucket in one prompt.
3. **Audit.** Write `merge_report.json`: every normalized form, seed decision, candidate
   pair, LLM decision/confidence/reason, source mentions, final cluster, model, prompt
   hash, unresolved candidates. **This step is the ceiling on the feature.**
4. **Invert and classify aliases.** For each canonical entity, collect `source_chunks:
   [doc_id_chunk_id]` from every raw record whose `resolved_name` maps to it. Build a
   global normalized-alias ownership table:
   - exclude `pronoun` mentions and bare generic titles from all queryable alias fields;
   - put canonical names, glossary aliases, and observed aliases owned by exactly one final
     entity in `aliases_normalized` for exact lookup;
   - when the same normalized named form is owned by multiple entities, keep it in
     `ambiguous_aliases` for query-conditioned BM25 matching, but never give it the
     exact-match boost;
   - record every exclusion and ambiguity decision in `merge_report.json`.
5. **Relations (the `global` substrate).** Canonicalize both endpoints, then aggregate each
   fact once by `(src_id, tgt_id)` into a **relation record**:
   - merge `keywords` (deduped) and aggregate `description` (LLM summary when several raw
     descriptions differ);
   - deduplicate `source_chunks`; keep `occurrence_count` and a `weight`
     (e.g. `occurrence_count`, used for ranking/capping);
   - store `src_name` / `tgt_name` (canonical) for endpoint-name matching.
   Relations become their own artifact `relations.json` (feeding `miles_guo_relations`) and
   are also projected into each endpoint's `edges[]` adjacency with `src_id`, `tgt_id`,
   `neighbour_id`, `relation_id`, and `direction` (`outgoing`/`incoming`). **Following
   LightRAG, the build keeps the full adjacency** (LightRAG stores the complete graph and
   bounds it only at query time); do not truncate edges at index build. `edges[]` is stored
   sorted by `(-occurrence_count, normalized neighbour name, neighbour_id)` so the query-time
   `top_k` bound (Phase C) takes the most-witnessed neighbours first. A large safety cap
   (e.g. 500) guards only against a pathological hub blowing up `_source` size; it is not the
   retrieval bound. Never replace relation evidence with every chunk of the neighbouring
   entity.
6. **Profile.** For each entity, feed its (deduped, truncated) source-chunk descriptions to
   `call_llm_with_fallback` → a `≤150`-char `profile`. Same truncation approach as
   `SummaryExtractor._truncate_text_by_tokens`
   ([summary_extractor.py:41-49](../../lib/data/summary_extractor.py#L41-L49)). Retrieval/
   index metadata only; never returned to the answer model as evidence.

Entity schema (`entities.json`, a list):
```json
{"entity_id":"person:2dc8...","canonical_name":"郭文贵","type":"person",
 "aliases":["郭先生","文贵","Miles Kwok","郭浩云"],
 "aliases_normalized":["郭先生","文贵","miles kwok","郭浩云"],
 "ambiguous_aliases":[],
 "profile":"郭文贵发起并资助法治基金，与班农合作……",
 "source_chunks":["doc12_3","doc12_4","doc88_0"],
 "edges":[{"relation_id":"rel:7f2a...","src_id":"person:2dc8...","tgt_id":"org:9a31...",
           "neighbour_id":"org:9a31...","direction":"outgoing","target_name":"法治基金",
           "occurrence_count":1}]}
```

Relation schema (`relations.json`, a list):
```json
{"relation_id":"rel:7f2a...","src_id":"person:2dc8...","tgt_id":"org:9a31...",
 "src_name":"郭文贵","tgt_name":"法治基金",
 "description":"郭文贵发起并资助法治基金",
 "keywords":["发起","资助"],
 "source_chunks":["doc12_3"],
 "occurrence_count":1,"weight":1.0}
```

`entity_id` is a stable SHA-256-derived identifier over `type + normalized canonical name`;
`relation_id` is derived over `src_id + tgt_id` (endpoints already canonical). Both are
**stable within a build**; a rebuild that changes the canonical representative may change
the id, which is why any config/corpus change triggers a full rebuild.

## Phase B — Elasticsearch indices

### B1. Entity write/read client — `lib/search/elastic_entity_index.py`

Mirror `ElasticChunk` / `ElasticWriteClientChunks`
([elastic_chunk_index.py:10-24](../../lib/search/elastic_chunk_index.py#L10-L24)).
`_id = entity_id`. Override `update_mappings`
([elastic_base.py:122-153](../../lib/search/elastic_base.py#L122-L153)):

```json
{ "properties": {
    "entity_id":          {"type":"keyword"},
    "canonical_name":     {"type":"text","fields":{"kw":{"type":"keyword"}}},
    "aliases":            {"type":"text","fields":{"kw":{"type":"keyword"}}},
    "aliases_normalized": {"type":"keyword"},
    "ambiguous_aliases":  {"type":"text"},
    "type":               {"type":"keyword"},
    "profile":            {"type":"text"},
    "source_chunks":      {"type":"keyword"},
    "edges":              {"type":"object","enabled":false} } }
```

`aliases_normalized` (keyword) supports deterministic exact lookup after application-side
normalization. `edges` stays in `_source` but is not indexed (adjacency is read from
`_source`, not queried).

### B2. Relation write/read client — `miles_guo_relations`

In the same module, add a relation write/read client. `_id = relation_id`. Mapping:

```json
{ "properties": {
    "relation_id":   {"type":"keyword"},
    "src_id":        {"type":"keyword"},
    "tgt_id":        {"type":"keyword"},
    "src_name":      {"type":"text","fields":{"kw":{"type":"keyword"}}},
    "tgt_name":      {"type":"text","fields":{"kw":{"type":"keyword"}}},
    "description":   {"type":"text"},
    "keywords":      {"type":"text"},
    "source_chunks": {"type":"keyword"},
    "weight":        {"type":"float"} } }
```

This is the **`global` retriever's index.** `description / keywords / src_name / tgt_name`
carry text mappings so high-level query keywords match relation semantics as far as BM25
allows; `src_id / tgt_id` keywords support exact endpoint filtering and graph joins.

`insert_entities()` / `insert_relations()` each recreate their index, apply the mapping,
and bulk-load the complete artifact. They may reuse the inherited bulk write machinery
([elastic_base.py:256-321](../../lib/search/elastic_base.py#L256-L321)), but v1 must not
incrementally upsert a new resolver build into a previous index, because removed or renamed
clusters would survive as stale documents. **Only the entity and relation indices are
recreated; the chunk index `miles_guo` is untouched.**

### B3. Register the indices

Add to [lib/index_mapping.json](../../lib/index_mapping.json) alongside `title_index`:
```json
"miles_guo": {
  "title_index": "miles_guo_titles",
  "entity_index": "miles_guo_entities",
  "relation_index": "miles_guo_relations",
  "doc_lang": "zh"
}
```
Update `get_index_meta()` to return optional `entity_index` and `relation_index`. Do not
derive fallbacks: absence means that dataset does not support entity/relation retrieval.
This prevents the globally registered skill from querying nonexistent indices for `lzj`,
`lxb`, `mzd`, or `hansard`.

## Phase C — Retrieval (local + global)

### C1. Read clients — `ElasticReadClientEntities` / `ElasticReadClientRelations`

In `elastic_entity_index.py`, mirror `ElasticReadClientChunks`
([elastic_chunk_index.py:298-407](../../lib/search/elastic_chunk_index.py#L298-L407)):

- **`search_entities(query, mentions, local_keywords, index, k)`** (`local`): normalize
  mentions/keywords; `bool.should` with exact `terms` on `aliases_normalized` (high boost)
  **plus** a query-conditioned `multi_match` over `canonical_name^3, aliases^2,
  ambiguous_aliases, profile`. Exact lookup applies only to aliases with one audited owner;
  ambiguous forms rely on the rest of the query. Returns entity docs.
- **`search_relations(query, global_keywords, index, k)`** (`global`): `bool.should` with a
  `multi_match` over `description^2, keywords^2, src_name, tgt_name`, using
  `global_keywords + query` as the text; optional exact `terms` on `src_name.kw / tgt_name.kw`
  when the query names an endpoint. Returns relation docs.

### C2. Orchestration — `ElasticMix.search_lightrag`

Add next to `search_2steps`
([elastic_mix.py:67-90](../../lib/search/elastic_mix.py#L67-L90)):

```python
async def search_lightrag(self, query, mentions, local_keywords, global_keywords,
                          entity_index, relation_index, chunk_index,
                          top_k=60, related_chunk_number=5):
    # local: entity match + one-hop relation expansion
    ents = await self.client_entity.search_entities(
        query, mentions, local_keywords, entity_index, k=top_k)
    # global: relation match + one-hop endpoint expansion
    rels = await self.client_relation.search_relations(
        query, global_keywords, relation_index, k=top_k)

    # one-hop expansion. Full adjacency is kept at build time; bound it HERE at query
    # time (top_k), the way LightRAG bounds its in-memory graph at query time.
    expanded_rel_ids = _dedup(
        [edge["relation_id"] for e in ents for edge in e["edges"]]
        + [r["relation_id"] for r in rels])[:top_k]
    all_rels = await self.client_relation.fetch_by_ids(relation_index, expanded_rel_ids)

    # LightRAG WEIGHT selection (vector-free): occurrence-count weighted polling.
    # Chunks are ranked by how many entities/relations cite them — NOT by BM25 — so an
    # alias-only chunk (query 「郭文贵」, chunk says only "Miles Kwok") is selected on its
    # citation weight instead of scoring 0 on lexical match and being buried.
    entity_sel   = pick_by_weighted_polling(
        ents,  source_key="source_chunks", max_related_chunks=related_chunk_number)
    # Relation channel dedups against the already-selected entity chunks BEFORE polling,
    # so it contributes only NEW chunks (LightRAG _find_related_text_unit_from_relations).
    relation_sel = pick_by_weighted_polling(
        all_rels, source_key="source_chunks", max_related_chunks=related_chunk_number,
        exclude=set(entity_sel))

    # Fetch chunk bodies by id, PRESERVING weighted-polling order (no score re-sort).
    entity_hits   = await self.client_chunk.fetch_chunks_by_ids(chunk_index, entity_sel)
    relation_hits = await self.client_chunk.fetch_chunks_by_ids(chunk_index, relation_sel)

    # Return the two ordered channels SEPARATELY — do NOT round-robin/cap here. The single
    # shared merge in rag_search_node interleaves entity + relation with the naive
    # (general_search) channel, mirroring LightRAG's _merge_all_chunks.
    return LightRAGChannels(entity=entity_hits, relation=relation_hits)
```

- **Vector-free chunk selection is LightRAG's own `WEIGHT` method, not BM25.**
  `pick_by_weighted_polling` (port of
  [utils.py:3991](https://github.com/HKUDS/LightRAG/blob/e9ddb8d46c55d3138663e7d0a4ca5ca2c05d4641/lightrag/utils.py))
  counts, per candidate chunk, how many of the matched entities/relations cite it, sorts each
  entity's/relation's chunks by that count, and allocates a **linear-decreasing quota**
  (`max_related_chunks=related_chunk_number` for the top-ranked entity down to
  `min_related_chunks=1`), redistributing leftover quota in a second pass. This is a strictly
  better fit for the alias-recall use case than the previously proposed BM25 ranking: the
  witnessing chunk is chosen on citation weight, so `minimum_should_match:0` / `(-score,…)`
  tie-break-by-`doc_id` (which would order an all-zero-score set arbitrarily) is not used at
  all.
- **Relation channel is deduped against the entity channel before polling.** Relation
  evidence is normally a subset of endpoint-entity evidence; LightRAG removes the
  already-selected entity chunks first (`exclude=`) so the relation/`global` channel
  contributes only new chunks and is provably not a no-op (lifecycle point 4).
- **`ElasticReadClientChunks.fetch_chunks_by_ids(index, ids)`** replaces the earlier
  BM25-ranking `search_chunks_by_ids`: it is a plain `_id`-filter fetch that returns chunk
  bodies **in the caller's (weighted-polling) order**, batching filters at 10,000 IDs. There
  is no query-conditioned re-scoring of the KG chunks — ordering authority is the weighted
  polling, exactly as in LightRAG's `WEIGHT` path. (The naive channel keeps its own BM25
  ordering; it comes from `general_search`, unchanged.)
- **Per-document cap and global `chunk_k`** are applied *once*, in the shared merge, to the
  final round-robin set (§Architecture), not inside `search_lightrag`.
- `search_lightrag` must never synthesize a profile or relation description into a result.
  Every returned result maps to an existing `_id` in the `miles_guo` chunk index.

## Phase D — Agentic integration

### D1. Skill — `lib/skills/lightrag_search.py`

Mirror `GeneralSearchSkill`
([general_search.py:43-101](../../lib/skills/general_search.py#L43-L101)).
`name = "lightrag_search"`. Input:
```python
class LightRAGSearchInput(SkillInput):
    query: str                    # complete user query, used to rank candidate chunks
    entity_mentions: list[str]    # named entities pulled from the query   (local)
    local_keywords: list[str]     # low-level / entity-oriented keywords   (local)
    global_keywords: list[str]    # high-level / relation-oriented keywords (global)
```
`execute()` reads `chunk_index` from `state["search_config"]`
([general_search.py:69-71](../../lib/skills/general_search.py#L69-L71)), derives
`entity_index` and `relation_index` via `get_index_meta`, and calls the `SearchService`
path down to `ElasticMix.search_lightrag`. Because the shared merge is a **single**
round-robin over three channels (naive/entity/relation, §Architecture), the skill exposes
its **entity-source and relation-source results as two ordered channels** rather than a
single pre-fused `DocumentResult[]`; each channel entry is still `DocumentResult`-shaped.
`rag_search_node` treats these two channels alongside `general_search`'s (naive) channel.
If `get_index_meta(chunk_index)` lacks `entity_index` **or** `relation_index`, return typed
empty channels rather than querying a derived index. Add a `lightrag_search` method to
`SearchService` to match the existing layering
([factory.py:8-13](../../lib/skills/factory.py#L8-L13)), then
`registry.register(LightRAGSearchSkill(search_service))` in
[factory.py:22-26](../../lib/skills/factory.py#L22-L26).

Graph expansion is part of the skill's normal execution, not an opt-in flag. There is no
`include_neighbours=False` default that keeps the graph dark; `local` and `global` both run,
and one-hop expansion is standard. Depth stays at one hop.

### D2. Entry and refinement routing

Prompt edits alone are insufficient because `entry_llm_node` currently exposes a classifier
schema without keyword/mention fields and hard-codes one `general_search` call
([entry_llm_node.py:69-100](../../lib/agentic/nodes/entry_llm_node.py#L69-L100),
[entry_llm_node.py:156-175](../../lib/agentic/nodes/entry_llm_node.py#L156-L175)).

- Add `entity_mentions`, `local_keywords`, `global_keywords` (each `list[str]`, normalized,
  deduped, capped at 5) to both the function-calling tool and the structured-output fallback
  in `lib/agentic/prompts/entry_prompt.py`.
- For `need_rag`, always plan `general_search`. Also plan `lightrag_search` when the dataset
  has both `entity_index` and `relation_index` and at least one of `entity_mentions /
  local_keywords / global_keywords` is nonempty.
- Add legacy `search_lightrag` support to `build_validation_tool()` and both legacy-op
  conversion helpers so the structured fallback can request the same path.
- After skill execution, call new `lib/search/result_merge.py::round_robin_merge` from
  `rag_search_node` **once**, over the three channels — `general_search` (naive),
  `lightrag_search`'s entity-source, and its relation-source — in LightRAG's
  naive→entity→relation order, deduping by `(doc_id, chunk_id)`, then apply the per-document
  cap and the global `chunk_k` budget. There is no second, intra-skill round-robin.

### D3. Prompts

- `prompts/zh/entry_prompt.yaml`: teach entry_llm to extract, for entity/relation/
  aggregation questions, three fields — `entity_mentions` (named things), `local_keywords`
  (entity-oriented low-level terms), and `global_keywords` (relation-oriented high-level
  terms, e.g. 资助/发起/对立). Mirror LightRAG's low-level/high-level keyword split
  ([extract_keywords_only, operate.py:4164](https://github.com/HKUDS/LightRAG/blob/e9ddb8d46c55d3138663e7d0a4ca5ca2c05d4641/lightrag/operate.py#L4164)).
- `prompts/zh/agentic_prompt.yaml`: let `reply_validation` re-issue `lightrag_search` with
  refined keywords on the refine loop when the first pass was entity/relation-thin. The
  `max_iter` guard already bounds this
  ([reply_validation](../architecture/agentic-pipeline.md#L112-L121)).
- Both prompts must describe results as original-source chunks and must not instruct the
  model to quote or cite entity profiles or relation descriptions.

## Phase E — Evaluation

Gate the feature on a real comparison, `miles_guo` only, using the dataset, metric
definitions, fusion contract, and acceptance thresholds already pinned in
[metrics.md](metrics.md). This plan does **not** invent its own thresholds; the numeric
gates are whatever `metrics.md` defines.

- **Question buckets** (used to structure both the exploratory smoke set and the audited
  ship set defined in `metrics.md`):
  1. **alias recall** — 「郭先生说了什么」 (query surface ≠ chunk surface);
  2. **entity summary / aggregation** — 「X 是谁 / 综述 X」 (`local`);
  3. **cross-entity relation** — 「谁资助了班农参与的项目 / A 和 B 什么关系」 (`global`).
  Bucket (3) is a **first-class** bucket here because `global`/relation retrieval is in
  scope; it is not merely "reported".
- **Compare:** `general_search` only vs `general_search + lightrag_search`.
- **Metrics:** the answer-bearing retrieval and answer-quality metrics and paired-bootstrap
  procedure from `metrics.md`. In addition, report the diagnostics specific to this feature:
  entity-match accuracy, relation-match accuracy, alias over-/under-merge rates, and
  retrieval / end-to-end latency percentiles. Whether any of these gates the ship decision,
  and at what level, is governed by `metrics.md` — not by numbers written here.
- **Entity/relation labels:** every audited ship row records `bucket`, `gold_entity_ids`,
  `gold_relation_ids` (bucket 3), `gold_alias_cluster`, and `relevant_chunk_ids`; persist
  the audited alias/relation pairs and judgments with the run artifact.

## Phase F — Tests and failure handling

All deterministic logic must be covered without Elasticsearch or network credentials:

- `test/test_entity_extractor.py`: target/context boundaries, evidence-span rejection,
  confidence threshold, relation endpoint validation, **relation-keyword extraction**,
  matching-manifest resume, and fail-closed on source/config hash changes;
- `test/test_entity_resolver.py`: NFKC/casefold normalization, seed must-/cannot-link,
  transitive cannot-link conflicts, union-order independence, uncertain pairs, type
  isolation, stable IDs, pronoun/generic-title exclusion, ambiguous-alias ownership,
  **relation aggregation by `(src_id, tgt_id)` with keyword/description merge and dedup
  source_chunks**, bidirectional edge provenance, and top-20 edge cap;
- `test/test_lightrag_search.py`: exact lookup for uniquely owned aliases, no exact boost
  for ambiguous aliases, **`global` relation matching over keywords/description/endpoint
  names**, **entity↔relation one-hop expansion** with query-time `top_k` adjacency bound,
  **occurrence-count weighted polling selection** (linear-gradient quota:
  `related_chunk_number` for the top candidate down to `min=1`, second-pass redistribution),
  **relation channel deduped against the entity channel before polling**, `fetch_chunks_by_ids`
  preserving polling order with no BM25 re-rank, batched ID filters, the two channels returned
  separately (not pre-fused), missing entity/relation index behaviour, and the guarantee that
  every result came from the chunk index;
- `test/test_result_merge.py`: `pick_by_weighted_polling` quota allocation and redistribution;
  **single** three-channel round-robin (naive/entity/relation) in naive→entity→relation order;
  cross-channel duplicate removal; stable tie-breaking; per-document cap and global `chunk_k`
  applied once; sequential indices; and proof that an alias-only chunk (BM25 score 0) is still
  selected by citation weight, plus that the relation channel is provably not a no-op after
  entity-channel dedup;
- extend `test/test_agentic.py`: primary and fallback entry schemas emit
  `entity_mentions / local_keywords / global_keywords`; supported datasets plan both
  skills, unsupported datasets plan only general search; validation fallback can re-issue
  `lightrag_search`;
- extend `test/test_elastic_mix.py`: `search_lightrag` preserves separate entity-source and
  relation-source ranks until fusion, proves the relation channel is not a no-op on an
  overlapping fixture, and never expands to all chunks of a neighbouring entity.

Offline extraction failures are written to `entities_errors.jsonl` with chunk ID, stage,
exception class, and retry count. Resume skips only validated completed records. Query-time
entity/relation index absence returns an empty typed result; Elasticsearch transport
failures remain skill errors and do not suppress successful general-search results.

## New / changed files (summary)

| File | Change |
|---|---|
| `lib/data/entity_extractor.py` | **new** — A1 chunk-level entity + relation (with keywords) extraction |
| `lib/data/entity_resolver.py` | **new** — A2 canonicalize + profile + relation aggregation |
| `data/data_miles/entity_build_manifest.json` | **generated** — source/prompt/schema/glossary/model hashes governing resume/rebuild |
| `lib/search/elastic_entity_index.py` | **new** — entity **and** relation write/read clients, mappings |
| `lib/search/entity_normalization.py` | **new** — shared NFKC/casefold normalization |
| `lib/search/result_merge.py` | **new** — pure `round_robin_merge` (3-channel, dedup, per-doc + `chunk_k` cap) **and** `pick_by_weighted_polling` (occurrence-count linear-gradient chunk selection, port of LightRAG `utils.py:3991`) |
| `lib/search/elastic_chunk_index.py` | add `fetch_chunks_by_ids` (plain `_id`-filter fetch, preserves caller order; **no** BM25 re-rank of KG chunks) |
| `lib/search/elastic_mix.py` | add `search_lightrag` (local + global + expansion) orchestration |
| `lib/search/search_service.py` | new `lightrag_search` method (mirror general_search) |
| `lib/skills/lightrag_search.py` | **new** — skill |
| `lib/skills/factory.py` | register the skill |
| `lib/index_mapping.py`, `lib/index_mapping.json` | expose optional `entity_index` + `relation_index`; configure only for `miles_guo` |
| `lib/agentic/nodes/entry_llm_node.py` | parse/cap mentions + local/global keywords; plan both retrieval skills |
| `lib/agentic/prompts/entry_prompt.py` | add the three fields to structured fallback schema |
| `lib/agentic/tools/validation_tool.py` | add legacy `lightrag_search` fallback contract |
| `lib/agentic/nodes/reply_validation_node.py` | convert fallback lightrag operations |
| `lib/agentic/nodes/rag_search_node.py` | retain per-skill ranks and apply global fusion/budget |
| `prompts/zh/entry_prompt.yaml`, `prompts/zh/agentic_prompt.yaml` | local/global keyword extraction + routing policy |
| `scripts/data_prepare_miles_entities.ipynb` | **new** — drive A1→A2→B (entities + relations) |
| `test/test_entity_extractor.py`, `test/test_entity_resolver.py` | **new** — offline pipeline tests |
| `test/test_lightrag_search.py`, `test/test_result_merge.py` | **new** — retrieval/merge tests |
| `test/test_agentic.py`, `test/test_elastic_mix.py` | extend routing/orchestration coverage |
| `docs/README_INDEX.md` | note `miles_guo` supports entity + relation retrieval |
| `docs/architecture/entity-graph-retrieval.md` | **new, required before ship** — permanent design history, LightRAG comparison, evidence policy, limitations, evaluation |
| `docs/architecture/rag-system.md`, `docs/README.md` | link the formal architecture document |

## Acceptance criteria

- [ ] `data/data_miles/entities.json` and `relations.json` built; every entity, edge, and
      relation source has a validated target-chunk evidence span; extraction errors and
      resume state are recorded; the build manifest matches every extraction record.
- [ ] `merge_report.json` spot-checked; the top entity clusters have no critical
      over-merges and measured under-merges are included in the evaluation report.
- [ ] `miles_guo_entities` and `miles_guo_relations` recreated from one complete resolver
      build with no stale records from an earlier build. No entity/relation-layer code has
      write access to `miles_guo`; before/after chunk-index mapping, doc count, and stable
      `_id + _source` content hash are identical.
- [ ] `lightrag_search` registered and callable; runs `local` **and** `global` with one-hop
      expansion, returns `DocumentResult`-shaped hits that pass through cross-skill round-robin/dedup,
      respect global `chunk_k`, and render in the existing frontend with no frontend change.
- [ ] Every `lightrag_search` result resolves to a real document in `miles_guo`; no entity
      profile or relation description is emitted as a synthetic `DocumentResult`.
- [ ] Cross-surface alias queries retrieve answer-bearing chunks with no literal query form
      — query 「郭文贵」 retrieves a gold chunk containing only "Miles Kwok", and the reverse.
- [ ] The `global` path demonstrably retrieves relation evidence: on a fixture where the two
      endpoints co-occur only through a relation, `global` surfaces the witnessing chunk that
      the `local`/entity path alone does not rank; entity-source and relation-source channels
      stay separate until fusion, and the relation channel is provably not a no-op.
- [ ] Evaluation runs under `metrics.md`'s dataset/manifest/metric/threshold rules; the
      exploratory smoke set is recorded as exploratory; the audited ship set passes the gates
      defined in `metrics.md`, with buckets (1)/(2)/(3) all reported.
- [ ] All Phase F tests pass without network credentials; an Elasticsearch-backed
      integration run confirms exact alias lookup, `global` relation matching, one-hop
      expansion, filtered BM25 ranking, and real IDs.
- [ ] `docs/architecture/entity-graph-retrieval.md` records the complete design history:
      original LightRAG local/global indexing/retrieval/context flow, the three deliberate
      divergences (vector-free matching, automatic alias canonicalization, chunks-only
      citation), known losses, and final evaluation. Architecture/doc indexes link to it.
- [ ] No change to `main.py`, the chunk/title indices, or the frontend beyond the
      dataset-capability note.

## Out of scope

- Any embedding / sparse encoder (explicitly rejected — see the borrow/drop table and
  [rag-system.md:84-119](../architecture/rag-system.md#L84-L119)). `global` is kept, but its
  matching substrate is BM25/exact, never a vector.
- Multi-hop graph traversal — one hop only (`local` entity→relation and `global`
  relation→endpoint expansion).
- Online incremental maintenance (document queue, per-document delete/rebuild). Any
  corpus/config change triggers a full rebuild of both artifacts and both indices.
- Rolling the layer out to `lzj` / `lxb` / `mzd` / `hansard` — prove it on `miles_guo`
  first, then templatize the notebook.
- Synthetic profile / relation-description results in the answer context. Profiles and
  relation descriptions remain retrieval metadata; original chunks are the only answer
  evidence.
- A learned or query-expanded relation-keyword layer to recover dense `global`'s paraphrase
  matching. Revisit only if Phase E shows a material bucket-(3) loss under `metrics.md`.
