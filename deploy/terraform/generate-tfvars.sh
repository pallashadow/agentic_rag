#!/bin/bash
# Generate terraform.tfvars from .env file
# Usage: ./generate-tfvars.sh

set -e

ENV_FILE="../../.env"
TFVARS_FILE="terraform.tfvars"

if [ ! -f "$ENV_FILE" ]; then
    echo "Error: $ENV_FILE not found!"
    echo "Please create a .env file in the project root first."
    exit 1
fi

echo "Generating terraform.tfvars from .env file..."
echo ""

# Load .env file
set -a
source "$ENV_FILE"
set +a

# Generate terraform.tfvars
cat > "$TFVARS_FILE" <<EOF
# Generated from .env file - DO NOT EDIT MANUALLY
# Run ./generate-tfvars.sh to regenerate

project_id = "${GCP_PROJECT_ID:-your-gcp-project-id}"
region     = "${GCP_REGION:-us-central1}"

# Function configuration
function_name = "chatbot-milesguo"
runtime       = "python311"
memory        = "256Mi"
timeout       = 300
max_instances = 10
min_instances = 0

# Source directory (relative to terraform directory)
source_dir = "../.."

# Use Secret Manager for API keys (recommended for production)
use_secret_manager = true

# Secret Manager secret IDs (if use_secret_manager = true)
openai_api_key_secret_id  = "openai-api-key"
google_api_key_secret_id  = "google-api-key"
elastic_url_secret_id     = "elastic-url"
elastic_api_key_secret_id  = "elastic-api-key"
api_auth_token_secret_id  = "api-auth-token"

# Direct environment variables (only used if use_secret_manager = false)
# WARNING: Not recommended for production - use Secret Manager instead
# openai_api_key  = ""
# google_api_key  = ""
# elastic_url     = ""
# elastic_api_key = ""
# api_auth_token  = ""

# Optional environment variables
cors_allow_origins   = "${CORS_ALLOW_ORIGINS:-*}"
rate_limit_per_minute = ${RATE_LIMIT_PER_MINUTE:-5}
rate_limit_per_hour   = ${RATE_LIMIT_PER_HOUR:-30}
EOF

echo "✓ Generated $TFVARS_FILE"
echo ""
echo "Review the file and run: terraform init && terraform plan"

