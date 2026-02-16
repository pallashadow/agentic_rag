# CI/CD Guide

This document explains the current automated release process (GitHub Actions) in this repository, including:

- Frontend deployment to GitHub Pages
- Backend deployment to Google Cloud Functions (Gen2)

Related workflow files:

- `.github/workflows/deploy-frontend.yml`
- `.github/workflows/deploy-backend.yml`

## 1. Pipeline Overview

### Frontend (GitHub Pages)

- Workflow: `deploy-frontend.yml`
- Primary goal: deploy the `frontend/` directory to GitHub Pages
- Deployment environment: `github-pages`

> **Important:** The frontend workflow does **not** run TypeScript build steps.
> It uploads `frontend/` as-is. If you changed files under `frontend/src/*.ts`,
> you must run `tsc -p frontend/tsconfig.json` locally and commit updated files
> under `frontend/dist/` before pushing, otherwise production pages will still use old JS.

### Backend (Google Cloud Functions)

- Workflow: `deploy-backend.yml`
- Primary goal: run `deploy/deploy.sh` to deploy the backend to GCP Cloud Functions
- Function name (hardcoded in script): `your-function-name`
- Region: `us-central1`

## 2. Trigger Rules

### Frontend Workflow Trigger (`deploy-frontend.yml`)

- `push` to `main` / `master` / `v2`
- `pull_request` closed with `merged == true`, targeting `main` / `master` / `v2`
- `workflow_dispatch` (manual trigger)

Additional notes:

- The `if` condition prevents accidental deployment when a PR is closed without being merged
- `concurrency: pages` keeps jobs in the same group serialized and does not cancel an in-progress Pages deployment

### Backend Workflow Trigger (`deploy-backend.yml`)

- `push` to `v2`
- `workflow_dispatch` (manual trigger)

## 3. Frontend Deployment Flow

Main steps in `deploy-frontend.yml`:

1. Checkout code (`actions/checkout@v4`)
2. Inject build metadata (UTC timestamp + Git SHA) into:
   - `frontend/rag.html`
   - `frontend/agentic.html`
3. Configure GitHub Pages (`actions/configure-pages@v4`)
4. Upload `frontend/` as the Pages artifact
5. Deploy to GitHub Pages (`actions/deploy-pages@v4`)

Build note:

- No `npm install`, `npm run build`, or `tsc` is executed in this workflow.
- Frontend JS must be prebuilt locally:
  - `tsc -p frontend/tsconfig.json`

## 4. Backend Deployment Flow

Main steps in `deploy-backend.yml`:

1. Checkout code (`actions/checkout@v4`)
2. Authenticate to GCP using Service Account JSON (`google-github-actions/auth@v2`)
3. Install and configure gcloud (`google-github-actions/setup-gcloud@v2`)
4. Set the GCP project
5. Create `.env` from GitHub Secrets
6. Run `bash deploy/deploy.sh`

Key behavior in `deploy/deploy.sh`:

- Load and export variables from `.env`
- Build `--set-env-vars` and run `gcloud functions deploy`
- If `CORS_ALLOW_ORIGINS` is empty, default to `https://pallashadow.github.io` to reduce frontend CORS failures
- Backend dependency source is `pyproject.toml` + `poetry.lock`; this repo does not maintain `requirements.txt`

## 5. Required GitHub Secrets

The backend workflow depends on these secrets:

- `GCP_SA_KEY`: GCP Service Account JSON content
- `GCP_PROJECT_ID`: target GCP project ID
- `OPENAI_API_KEY`
- `GOOGLE_API_KEY`
- `ELASTIC_URL`
- `ELASTIC_API_KEY`
- `API_AUTH_TOKEN` (optional but recommended)
- `CORS_ALLOW_ORIGINS` (optional, script has a default if not set)

## 6. Manual Release

You can manually run these workflows in GitHub Actions:

- `Deploy to GitHub Pages`
- `Deploy Backend (Cloud Functions)`

Recommended cases for manual release:

- You changed workflow/secrets configuration and need to validate the release pipeline
- You need to deploy outside normal trigger timing

## 7. Troubleshooting

### Frontend deploy succeeded but page did not update

- Confirm the URL path is correct (for example, `.../agentic.html`)
- Check browser cache and force refresh
- Verify in Actions that the latest run reached `Deploy to GitHub Pages`
- If you changed `frontend/src/*.ts`, confirm you rebuilt and committed `frontend/dist/*.js`

### Backend deploy failed (authentication related)

- Ensure `GCP_SA_KEY` is a complete and valid JSON
- Ensure the Service Account has required permissions for Cloud Functions/Cloud Run/Artifact Registry
- Ensure `GCP_PROJECT_ID` matches the target project
- Ensure these APIs are enabled in the target project:
  - `cloudresourcemanager.googleapis.com`
  - `cloudfunctions.googleapis.com`
  - `run.googleapis.com`
  - `cloudbuild.googleapis.com`
  - `artifactregistry.googleapis.com`
  - `serviceusage.googleapis.com`

### Backend deploy succeeded but requests fail

- Check whether `.env`-related secrets are missing or incorrect
- Check whether `CORS_ALLOW_ORIGINS` includes the current frontend origin
- Check function logs for runtime exceptions

## 8. Suggested Improvement (Optional)

The backend auto-deploy currently listens only to the `v2` branch. To align with frontend strategy, you may extend `deploy-backend.yml` triggers to:

- `main`
- `master`
- `v2`

Then combine this with branch protection rules to keep releases safe.


