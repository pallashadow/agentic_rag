# chatbot_milesguo

This is a demonstration of using RAG + LLM to build a chatbot, written in Python with Jupyter Notebooks.  
author: pannixilin  
Gettr: [@pannixilin1](https://gettr.com/user/pannixilin1)  




## Installation

1. Install Python libraries: `pip install -r requirements.txt`
2. Set up API keys:
   - Copy `env.example` to `.env`
   - Add your API keys:
     - `OPENAI_API_KEY`: For OpenAI API access
     - `GOOGLE_API_KEY`: For Google/Gemini API access (optional)
     - `ELASTIC_URL`: Elasticsearch server URL
     - `ELASTIC_API_KEY`: Elasticsearch API key
3. Set up Elasticsearch: The project uses Elasticsearch Serverless for document indexing and search
4. Prepare data: Run one of the notebooks in `scripts/` (e.g. `scripts/data_prepare_miles.ipynb`) to download and process the data

## Usage

### Data Preparation
Run one of the dataset-specific notebooks in `scripts/` (for example `scripts/data_prepare_miles.ipynb`) to:
- Download text from [`gwins.org`](https://gwins.org/)
- Process and split text into chunks
- Generate summaries and titles
- Index documents in Elasticsearch

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

For detailed technical documentation about the RAG algorithm, workflow, document expansion techniques, and design decisions, see [docs/README_RAG.md](docs/README_RAG.md).

### Agentic RAG

The project also includes an **Agentic RAG Pipeline** built with LangGraph that intelligently routes queries through different processing paths with iterative answer refinement. For detailed documentation about the agentic workflow, nodes, routing functions, and state management, see [docs/README_AGENTIC.md](docs/README_AGENTIC.md).

## Deployment

**Production Architecture:**
- **Frontend**: Static web frontend hosted on GitHub Pages (github.io)
- **Backend API**: Google Cloud Functions (2nd gen)
- **Database**: Elasticsearch Serverless
- **LLM**: Primary ChatGPT (GPT-4o-mini) with fallback to Gemini 2.0 Flash

**Recommended: Google Cloud Functions (2nd gen)**

The easiest way to deploy is using Google Cloud Functions. See [docs/README_GCLOUD_FUNCTIONS.md](docs/README_GCLOUD_FUNCTIONS.md) for deployment instructions.

The project includes `main.py` which contains the FastAPI app for Cloud Functions compatibility.

~~**Alternative deployment options (archived):**
- [archive/README_DOCKER.md](archive/README_DOCKER.md) - Docker deployment guide
- [archive/README_GCLOUD_RUN.md](archive/README_GCLOUD_RUN.md) - Google Cloud Run deployment guide~~

## Documentation

- [docs/README_zh.md](docs/README_zh.md) - 中文文档 (Chinese documentation)
- [docs/README_RAG.md](docs/README_RAG.md) - RAG algorithm, workflow, and design decisions
- [docs/README_AGENTIC.md](docs/README_AGENTIC.md) - Agentic RAG Pipeline documentation (LangGraph-based workflow)
- [docs/README_API.md](docs/README_API.md) - API endpoints and usage
- [docs/README_DATA.md](docs/README_DATA.md) - Data preparation guide and `data_*/` directory structure
- [docs/README_GCLOUD_FUNCTIONS.md](docs/README_GCLOUD_FUNCTIONS.md) - Google Cloud Functions deployment (recommended)
- [docs/README_TEST.md](docs/README_TEST.md) - Testing documentation
- [frontend/README_WEB.md](frontend/README_WEB.md) - Frontend documentation
- [archive/README_GCLOUD_RUN.md](archive/README_GCLOUD_RUN.md) - Google Cloud Run deployment (archived)
- [archive/README_DOCKER.md](archive/README_DOCKER.md) - Docker deployment guide (archived)

## Frontend (static)

The frontend is automatically deployed to GitHub Pages via GitHub Actions workflow (`.github/workflows/deploy.yml`). Every time code is merged to `main`, `master`, or `v2` branch, the frontend is automatically updated on GitHub Pages.

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
chatbot_milesguo/
  main.py                      # FastAPI app entry point (also used for Cloud Functions)
  requirements.txt             # Runtime dependencies
  requirements-dev.txt         # Dev dependencies
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
    entry_prompt.yaml
    rag.yaml
    agentic_prompt.yaml

  docs/                        # Documentation
    README_RAG.md
    README_AGENTIC.md
    README_API.md
    README_DATA.md
    README_TEST.md
    README_GCLOUD_FUNCTIONS.md
    README_zh.md

  frontend/                    # Static frontend (GitHub Pages)
    rag.html                   # Traditional RAG UI
    agentic.html               # Agentic RAG UI
    rag.js                     # Traditional RAG client logic
    agentic.js                 # Agentic RAG client logic
    common.js                  # Shared UI/client helpers
    styles.css
    README_WEB.md

  scripts/                     # Notebooks and helper scripts
    data_prepare_*.ipynb        # Data preparation per dataset (miles/lxb/lzj/mzd)
    playground_rag.ipynb        # RAG playground
    playground_agentic.ipynb    # Agentic workflow playground
    playground_agentic_stream.ipynb  # Agentic streaming playground
    graph.mmd                   # Mermaid graph diagram
    deploy.sh                   # Deployment helper

  test/                        # Unit/integration tests

  data/                        # Local datasets root
    data_*/                    # Per-dataset data (documents/chunks/summaries/titles, etc.)
  archive/                     # Archived deployment artifacts and old server
```

## Architecture

The system implements a **two-step RAG architecture**. For detailed documentation, see [docs/README_RAG.md](docs/README_RAG.md).

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


