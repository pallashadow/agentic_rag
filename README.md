# Agentic Rag Demo

This is a demonstration of using Agentic RAG to chat with documents
author: pannixilin (a.k.a. pannixilin1 / pannixilinNFSC / Yuhao Lu — the same person)  
Gettr: [@pannixilin1](https://gettr.com/user/pannixilin1)  
github: https://github.com/pallashadow/agentic_rag
frontend: https://pallashadow.github.io/agentic_rag/agentic.html

Tech stack: 
- **Backend Framework**: FastAPI (Python web framework)
- **LLM Integration**: LiteLLM (with fallback support for GPT-4o-mini and Gemini 2.0 Flash)
- **Agentic Workflow**: LangGraph (for building stateful agent workflows)
- **Search Engine**: Elasticsearch Serverless
- **Text Processing**: LangChain text splitters
- **Data Processing**: Python 3.11+, Jupyter Notebooks
- **Web Scraping**: BeautifulSoup4
- **PDF Processing**: PyPDF
- **Frontend**: Static HTML/JavaScript (hosted on GitHub Pages)
- **Deployment**: Google Cloud Functions (2nd gen), Terraform (optional IaC)
- **Protocol**: MCP (Model Context Protocol) for external integrations
- **Function Calling**: Native LLM function calling via LiteLLM (replaces JSON Schema structured outputs for better reliability)
- **Skills System**: Agent-native cognitive capability layer where LLMs can dynamically select and execute search skills (general_search, doc_search, neighbour_search)
- **Observability**: LangSmith integration for tracing API requests, LangGraph execution paths, and LLM calls with metadata and fallback tracking



## Installation

1. Install Python dependencies with Poetry: `poetry install`
2. Set up API keys:
   - Copy `env.example` to `.env`
   - Add your API keys:
     - `OPENAI_API_KEY`: For OpenAI API access
     - `GOOGLE_API_KEY`: For Google/Gemini API access (optional)
     - `ELASTIC_URL`: Elasticsearch server URL
     - `ELASTIC_API_KEY`: Elasticsearch API key
3. Set up Elasticsearch: The project uses Elasticsearch Serverless for document indexing and search
4. (Optional) Set up LangSmith observability:
   - `LANGSMITH_API_KEY`: LangSmith API key (get from https://smith.langchain.com)
   - `LANGSMITH_TRACING`: Set to `"true"` to enable tracing
   - `LANGSMITH_PROJECT`: Project name (use different projects for dev/staging/prod, e.g., `chatbot-milesguo-dev`)
   - `LANGSMITH_ENDPOINT`: LangSmith API endpoint (default: `https://api.smith.langchain.com`)
5. Prepare data: drive the reusable ingestion components in `lib/data/` (downloader, chunker, summary/title/context extractors) to populate Elasticsearch. The per-dataset orchestration notebooks are not tracked in this repo — see the Data Preparation section below.

Dependency management note: this project uses `pyproject.toml` + `poetry.lock`. `requirements.txt` is not maintained.

## Usage

### Data Preparation
The data-side pipeline is assembled from reusable components in `lib/data/`, run once per dataset (`chunk_index`) to populate Elasticsearch:
- **Download** — `downloader_miles.py` (`MilesGuoDataDownloader`) scrapes source text from [`gwins.org`](https://gwins.org/). This downloader is specific to the `miles_guo` dataset; other datasets (`lzj`, `lxb`, `mzd`, `epstein9`) are sourced separately.
- **Chunk** — `chunker.py` (`NaiveChunker`) splits documents into overlapping chunks.
- **Summaries / titles** — `summary_extractor.py` and `title_extractor.py` generate per-document summaries and titles, indexed into the `*_titles` index (via `ElasticWriteClientTitles`) for two-step retrieval.
- **Context expansion** — `contexter.py` (`ContextGenerator`) generates expanded context around chunks.
- **Index** — chunks are written via the chunk index client in `lib/search/`.

Each `chunk_index` is prepared **independently**, which is why the supported operations differ per dataset (e.g. some indices have summaries, some don't) — see [docs/README_INDEX.md](docs/README_INDEX.md) for the per-index capability list. The per-dataset notebooks that wired these components together are not tracked in this repo.

### Playground
Open one of the playground notebooks in `scripts/` to:
- Explore Elasticsearch search functionality
- Test title search and chunk search
- Experiment with the two-step search system

### Traditional RAG Chatbot
The RAG system uses:
- **Two-step retrieval**: First searches document titles/summaries, then retrieves relevant chunks
- **Multi-model LLM**: Uses LiteLLM with fallback support (GPT-4o-mini, Gemini 2.0 Flash)
- **Async processing**: Supports asynchronous API calls for better performance

For detailed technical documentation about the RAG algorithm, workflow, document expansion techniques, and design decisions, see [docs/architecture/rag-system.md](docs/architecture/rag-system.md).

### Agentic RAG

The project also includes an **Agentic RAG Pipeline** built with LangGraph that intelligently routes queries through different processing paths with iterative answer refinement. For detailed documentation about the agentic workflow, nodes, routing functions, and state management, see [docs/architecture/agentic-pipeline.md](docs/architecture/agentic-pipeline.md).

**Key Features:**

- **Function Calling**: The agentic workflow uses native LLM function calling (via LiteLLM) instead of JSON Schema structured outputs. This provides better reliability and automatic function call handling. Function calling is used in:
  - `entry_llm_node`: Classifies user queries and generates expanded queries
  - `reply_validation_node`: Validates answers and plans search operations
  - Query expansion: Dynamically expands short queries for better search coverage

- **Skills System**: The system implements an agent-native cognitive capability layer where skills are LLM-visible capabilities that can be dynamically selected and executed:
  - **general_search**: Semantic search with query expansion and two-step retrieval
  - **doc_search**: Search within a specific document
  - **neighbour_search**: Search neighboring chunks around a specific chunk
  - Skills export OpenAI-compatible tool schemas for LLM function calling
  - Skills are registered in `SkillRegistry` and can be extended with new capabilities
  - The LLM selects appropriate skills based on the query context and reasoning

- **LangSmith Observability**: When enabled, LangSmith provides comprehensive tracing for:
  - API request-level traces (`/chatbot`, `/agentic_rag`, streaming endpoints)
  - LangGraph execution paths (node loops, retries, iterations)
  - LiteLLM model calls (model name, fallback path, latency, token usage)
  - Production troubleshooting metadata (query type, search count, endpoint, version)

## Deployment

**Production Architecture:**
- **Frontend**: Static web frontend hosted on GitHub Pages (github.io)
- **Backend API**: Google Cloud Functions (2nd gen)
- **Database**: Elasticsearch Serverless
- **LLM**: Primary ChatGPT (GPT-4o-mini) with fallback to Gemini 2.0 Flash

**Recommended: Google Cloud Functions (2nd gen)**

The easiest way to deploy is using Google Cloud Functions. See [docs/guides/deploy-cloud-functions.md](docs/guides/deploy-cloud-functions.md) for deployment instructions.

The project includes `main.py` which contains the FastAPI app for Cloud Functions compatibility.

  - **Infrastructure as Code: Terraform (optional)**  
    For infrastructure-as-code deployment with version control and Secret Manager integration, see [deploy/terraform/README.md](deploy/terraform/README.md). Terraform configuration manages Cloud Functions, secrets, IAM permissions, and required GCP APIs.


~~**Alternative deployment options (archived):**
- [archive/docker.md](archive/docker.md) - Docker deployment guide
- [archive/cloud-run.md](archive/cloud-run.md) - Google Cloud Run deployment guide~~


## Documentation

Full index: **[docs/README.md](docs/README.md)**. Organized into three groups:

- **Architecture** ([docs/architecture/](docs/architecture/)) — [rag-system.md](docs/architecture/rag-system.md), [agentic-pipeline.md](docs/architecture/agentic-pipeline.md)
- **Guides** ([docs/guides/](docs/guides/)) — [api.md](docs/guides/api.md), [data-preparation.md](docs/guides/data-preparation.md), [testing.md](docs/guides/testing.md), [web.md](docs/guides/web.md), [ci-cd.md](docs/guides/ci-cd.md), [deploy-cloud-functions.md](docs/guides/deploy-cloud-functions.md)
- **Plan** ([docs/plan/](docs/plan/)) — planned upgrades ([hansard-index.md](docs/plan/hansard-index.md), [metrics.md](docs/plan/metrics.md), [frontend-react.md](docs/plan/frontend-react.md))

Archived deployment guides live in [archive/](archive/) ([docker.md](archive/docker.md), [cloud-run.md](archive/cloud-run.md)).

## Frontend (static)

The frontend is automatically deployed to GitHub Pages via GitHub Actions workflow (`.github/workflows/deploy-frontend.yml`). Every time code is merged to `main`, `master`, or `v2` branch, the frontend is automatically updated on GitHub Pages.

**Local Development:**
Open `frontend/rag.html` (traditional RAG) or `frontend/agentic.html` (agentic RAG) in a browser, set the Cloud Functions base URL + function name, then start chatting.

*Important:* To avoid CORS blocking, make sure the backend has CORS enabled. Configure `CORS_ALLOW_ORIGINS` in your `.env` file (e.g., `CORS_ALLOW_ORIGINS=*` or specific origins like `CORS_ALLOW_ORIGINS=https://yourusername.github.io,file://`).

**Automatic Deployment:**
- The workflow triggers on push/merge to main/master/v2 branches
- Frontend files are automatically deployed to GitHub Pages
- Build timestamp and Git SHA are injected into the HTML

Note: browser calls require CORS. This repo enables CORS via FastAPI `CORSMiddleware` and supports configuring allowed origins with `CORS_ALLOW_ORIGINS` ("*" or comma-separated).

## Project Structure

```
project_root/
  main.py                      # FastAPI app entry point (also used for Cloud Functions)
  pyproject.toml               # Python dependencies and project metadata
  env.example                  # Environment variables template
  LICENSE

  lib/                         # Core Python packages (RAG, search, agentic workflow, etc.)
    agentic/                   # LangGraph-based Agentic RAG pipeline
      nodes/                   # Graph nodes (entry, search, reply, validation)
      prompts/                 # Agentic prompt loaders + templates
      streaming.py             # Streaming helpers for agentic runs
    rag/                       # Traditional RAG implementation (prompting + query expansion)
    search/                    # Elasticsearch clients & indexing helpers
    llm/                       # LLM integration (LiteLLM wrapper)
    data/                      # Data download + preprocessing pipeline pieces
    security/                  # CORS/auth helpers for the API
    app_logger.py              # Logging utilities

  prompts/                     # YAML prompts used by the runtime
    zh/                        # Chinese prompts
      entry_prompt.yaml
      rag.yaml
      agentic_prompt.yaml
    en/                        # English prompts
      entry_prompt.yaml
      rag.yaml
      agentic_prompt.yaml

  docs/                        # Documentation (see docs/README.md for the index)
    README.md                  # Documentation index
    README_INDEX.md            # Dataset / chunk_index catalog (runtime asset, loaded by frontend)
    architecture/              # How the system works
      rag-system.md
      agentic-pipeline.md
    guides/                    # How to use and operate
      api.md
      data-preparation.md
      testing.md
      web.md
      ci-cd.md
      deploy-cloud-functions.md
    plan/                      # Planned upgrades
      hansard-index.md
      metrics.md
      frontend-react.md

  frontend/                    # Static frontend (GitHub Pages)
    rag.html                   # Traditional RAG UI
    agentic.html               # Agentic RAG UI
    rag.js                     # Traditional RAG client logic
    agentic.js                 # Agentic RAG client logic
    common.js                  # Shared UI/client helpers
    styles.css

  scripts/                     # Notebooks and helper scripts
    data_prepare_*.ipynb        # Data preparation per dataset (miles/lxb/lzj/mzd)
    playground_rag.ipynb        # RAG playground
    playground_agentic.ipynb    # Agentic workflow playground
    playground_agentic_stream.ipynb  # Agentic streaming playground
    graph.mmd                   # Mermaid graph diagram

  deploy/                      # Deployment configurations
    deploy.sh                   # Simple gcloud deployment script
    terraform/                  # Terraform IaC configuration

  test/                        # Unit/integration tests

  data/                        # Local datasets root
    data_*/                    # Per-dataset data (documents/chunks/summaries/titles, etc.)
  archive/                     # Archived deployment artifacts and old server
```

## Architecture

The system implements a **two-step RAG architecture**. For detailed documentation, see [docs/architecture/rag-system.md](docs/architecture/rag-system.md).

## Advantages vs. Naive RAG

Compared to a naive RAG baseline (search all chunks globally → stuff top-k into the prompt), this system is designed to be more robust on large, noisy Chinese corpora:

- **Higher recall with less noise**: Two-step retrieval (document-level title/summary → chunk-level search within those documents) reduces the search space and helps prevent relevant chunks from being drowned out by global chunk noise.
- **Better semantic matching without embeddings**: Index-time document expansion (`doc_summary`) and chunk-level contextual descriptions (`context`) are included in Elasticsearch `multi_match` queries, improving matches even when exact keywords are missing from the chunk text.
- **More stable for short queries**: Optional query expansion for very short inputs improves search coverage and reduces “too vague to retrieve” failures.
- **Lower token waste**: Deduplication by `doc_id_chunk_id` prevents redundant chunks from being sent to the LLM, reducing prompt size and cost.
- **Good latency characteristics**: Searches are executed asynchronously in parallel (naive + two-step, across expanded queries), improving end-to-end response time under the same retrieval budget.
- **Simpler operations**: No embedding model, vector index, or reranker service to run and monitor—only Elasticsearch Serverless plus LLM calls (with model fallback).

### Technology Stack

- **Frontend**: Static web (hosted on GitHub Pages)
- **Backend**: Google Cloud Functions (FastAPI)
- **Search**: Elasticsearch Serverless
- **LLM**: LiteLLM with primary ChatGPT (GPT-4o-mini) and fallback Gemini 2.0 Flash
- **Text Processing**: LangChain text splitters
- **Data Processing**: Python with Jupyter Notebooks  


