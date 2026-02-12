#!/bin/bash
# Helper script to initialize Secret Manager secrets
# Usage: ./init-secrets.sh [PROJECT_ID]
# If PROJECT_ID is not provided, will try to read from ../../.env (GCP_PROJECT_ID)

set -e

# Try to get PROJECT_ID from various sources
if [ -n "$1" ]; then
    PROJECT_ID="$1"
elif [ -n "$GOOGLE_CLOUD_PROJECT" ]; then
    PROJECT_ID="$GOOGLE_CLOUD_PROJECT"
elif [ -f "../../.env" ]; then
    # Try to read from .env file
    PROJECT_ID=$(grep "^GCP_PROJECT_ID=" ../../.env | cut -d'=' -f2- | tr -d '"' | tr -d "'" | xargs)
fi

if [ -z "$PROJECT_ID" ] || [ "$PROJECT_ID" = "your-gcp-project-id" ]; then
    echo "Error: PROJECT_ID is required"
    echo "Usage: ./init-secrets.sh PROJECT_ID"
    echo "Or set GCP_PROJECT_ID in ../.env file"
    echo "Or set GOOGLE_CLOUD_PROJECT environment variable"
    exit 1
fi

echo "Initializing Secret Manager secrets for project: $PROJECT_ID"
echo ""

# Check if .env file exists
if [ ! -f "../.env" ]; then
    echo "Warning: ../.env file not found"
    echo "You can create secrets manually or provide values interactively"
    echo ""
fi

# Function to create or update secret
create_secret() {
    local secret_name=$1
    local env_var_name=$2  # Variable name in .env file (e.g., OPENAI_API_KEY)
    local description=$3
    local prompt=$4
    
    if gcloud secrets describe "$secret_name" --project="$PROJECT_ID" &>/dev/null; then
        echo "Secret '$secret_name' already exists. Skipping..."
    else
        echo "Creating secret: $secret_name"
        if [ -f "../.env" ]; then
            # Try to extract from .env file using the correct variable name
            local value=$(grep "^${env_var_name}=" ../.env | cut -d'=' -f2- | tr -d '"' | tr -d "'" | xargs)
            if [ -n "$value" ] && [ "$value" != "" ]; then
                echo -n "$value" | gcloud secrets create "$secret_name" \
                    --project="$PROJECT_ID" \
                    --data-file=- \
                    --replication-policy="automatic" \
                    --labels="managed-by=terraform"
                echo "  ✓ Created from .env file (${env_var_name})"
            else
                echo "  Secret not found in .env (${env_var_name}), creating empty secret"
                echo "" | gcloud secrets create "$secret_name" \
                    --project="$PROJECT_ID" \
                    --data-file=- \
                    --replication-policy="automatic" \
                    --labels="managed-by=terraform"
                echo "  ⚠ Please update the secret value:"
                echo "    echo -n 'your-value' | gcloud secrets versions add $secret_name --project=$PROJECT_ID --data-file=-"
            fi
        else
            # Create empty secret
            echo "" | gcloud secrets create "$secret_name" \
                --project="$PROJECT_ID" \
                --data-file=- \
                --replication-policy="automatic" \
                --labels="managed-by=terraform"
            echo "  ⚠ Empty secret created. Please update:"
            echo "    echo -n 'your-value' | gcloud secrets versions add $secret_name --project=$PROJECT_ID --data-file=-"
        fi
    fi
    echo ""
}

# Create secrets
# Parameters: secret_name, env_var_name, description, prompt
create_secret "openai-api-key" "OPENAI_API_KEY" "OpenAI API Key" "Enter your OpenAI API key"
create_secret "google-api-key" "GOOGLE_API_KEY" "Google API Key" "Enter your Google/Gemini API key"
create_secret "elastic-url" "ELASTIC_URL" "Elasticsearch URL" "Enter your Elasticsearch URL"
create_secret "elastic-api-key" "ELASTIC_API_KEY" "Elasticsearch API Key" "Enter your Elasticsearch API key"

# Optional: API auth token
read -p "Do you want to create api-auth-token secret? (y/N): " -n 1 -r
echo
if [[ $REPLY =~ ^[Yy]$ ]]; then
    create_secret "api-auth-token" "API_AUTH_TOKEN" "API Auth Token" "Enter your API auth token"
fi

echo "=== Secret initialization complete ==="
echo ""
echo "Next steps:"
echo "1. Update secret values if needed:"
echo "   echo -n 'value' | gcloud secrets versions add SECRET_NAME --project=$PROJECT_ID --data-file=-"
echo ""
echo "2. Run terraform init and terraform apply"
echo "   cd terraform"
echo "   terraform init"
echo "   terraform apply"

