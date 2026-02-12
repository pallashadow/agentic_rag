#!/bin/bash
# Load .env file and deploy
# Run from project root: ./deploy/deploy.sh

set -e  # Exit on error

# Get the project root directory (parent of deploy/)
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"

cd "$PROJECT_ROOT"

echo "=== Starting deployment to Google Cloud Functions ==="

# Check if .env file exists
if [ ! -f .env ]; then
    echo "Error: .env file not found!"
    echo "Please create a .env file with required environment variables."
    exit 1
fi

echo "Loading environment variables from .env file..."
# Load .env file more safely
set -a  # Automatically export all variables
source .env
set +a

# Verify required environment variables are set
if [ -z "$OPENAI_API_KEY" ] || [ -z "$GOOGLE_API_KEY" ] || [ -z "$ELASTIC_URL" ] || [ -z "$ELASTIC_API_KEY" ]; then
    echo "Warning: Some required environment variables may be missing!"
    echo "Required: OPENAI_API_KEY, GOOGLE_API_KEY, ELASTIC_URL, ELASTIC_API_KEY"
fi

echo "Deploying function (this may take 5-15 minutes)..."
echo "Function: chatbot-milesguo"
echo "Region: us-central1"
echo "Runtime: python311"
echo ""

# Show active gcloud identity for easier CI debugging.
ACTIVE_ACCOUNT="$(gcloud config get-value account 2>/dev/null || true)"
ACTIVE_PROJECT="$(gcloud config get-value project 2>/dev/null || true)"
echo "gcloud account: ${ACTIVE_ACCOUNT:-<unknown>}"
echo "gcloud project: ${ACTIVE_PROJECT:-<unknown>}"

# Fail early with a clear action list if project access is unavailable.
# Motivation: CI often fails late during deploy with less actionable output.
if ! gcloud projects describe "$ACTIVE_PROJECT" --format='value(projectNumber)' >/dev/null 2>&1; then
    echo ""
    echo "Error: Unable to access GCP project '$ACTIVE_PROJECT'."
    echo "Please check all of the following before retrying:"
    echo "  1) cloudresourcemanager.googleapis.com is enabled on the project"
    echo "  2) This service account can access the project (at least Viewer/Browser)"
    echo "  3) The credentials file points to the intended deploy service account"
    exit 1
fi

# Build environment variables string
ENV_VARS="OPENAI_API_KEY=$OPENAI_API_KEY,GOOGLE_API_KEY=$GOOGLE_API_KEY,ELASTIC_URL=$ELASTIC_URL,ELASTIC_API_KEY=$ELASTIC_API_KEY"

# Add optional variables if they exist
if [ -n "$API_AUTH_TOKEN" ]; then
    ENV_VARS="$ENV_VARS,API_AUTH_TOKEN=$API_AUTH_TOKEN"
fi

# Always set CORS explicitly to avoid environment drift between deployments.
# Motivation: missing/empty CORS value is a common reason for browser-side failures.
if [ -z "$CORS_ALLOW_ORIGINS" ]; then
    CORS_ALLOW_ORIGINS="https://pallashadow.github.io"
    echo "CORS_ALLOW_ORIGINS is empty; defaulting to $CORS_ALLOW_ORIGINS"
fi
ENV_VARS="$ENV_VARS,CORS_ALLOW_ORIGINS=$CORS_ALLOW_ORIGINS"
echo "Effective CORS_ALLOW_ORIGINS: $CORS_ALLOW_ORIGINS"

# Deploy with verbose output
gcloud functions deploy chatbot-milesguo \
  --quiet \
  --gen2 \
  --runtime python311 \
  --region us-central1 \
  --source . \
  --trigger-http \
  --allow-unauthenticated \
  --memory 256Mi \
  --timeout 300s \
  --max-instances 10 \
  --set-env-vars "$ENV_VARS" \
  --verbosity=info

echo ""
echo "=== Deployment completed successfully! ==="

