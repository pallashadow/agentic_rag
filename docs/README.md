# Documentation

Index of project documentation. Grouped by intent.

## Architecture — how the system works
- [architecture/rag-system.md](architecture/rag-system.md) — RAG algorithm, two-step retrieval, query expansion, design decisions
- [architecture/agentic-pipeline.md](architecture/agentic-pipeline.md) — LangGraph agentic workflow: nodes, routing, state management

## Guides — how to use and operate
- [guides/api.md](guides/api.md) — API endpoints and usage
- [guides/data-preparation.md](guides/data-preparation.md) — data pipeline and `data_*/` directory structure
- [guides/testing.md](guides/testing.md) — running the test suite
- [guides/web.md](guides/web.md) — static frontend usage and configuration
- [guides/ci-cd.md](guides/ci-cd.md) — GitHub Actions release process
- [guides/deploy-cloud-functions.md](guides/deploy-cloud-functions.md) — Google Cloud Functions deployment (recommended)

## Plan — planned upgrades
- [plan/README.md](plan/README.md) — remaining modernization work
- [plan/hansard-index.md](plan/hansard-index.md) — add a UK Parliament Hansard (English) chunk_index
- [plan/metrics.md](plan/metrics.md) — offline evaluation framework
- [plan/frontend-react.md](plan/frontend-react.md) — migrate frontend to React

## Reference
- [../deploy/terraform/README.md](../deploy/terraform/README.md) — Terraform infrastructure-as-code
- [../archive/](../archive/) — archived deployment guides (Docker, Cloud Run)

> Note: `README_INDEX.md` in this directory is not documentation — it is the dataset/`chunk_index` catalog loaded at runtime by the frontend and synced by CI. Do not rename it.
