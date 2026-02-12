# 1. Enable required APIs
resource "google_project_service" "required_apis" {
  for_each = toset([
    "cloudfunctions.googleapis.com",
    "cloudbuild.googleapis.com",
    "secretmanager.googleapis.com",
    "run.googleapis.com",
    "storage.googleapis.com"
  ])

  project = var.project_id
  service = each.value

  disable_on_destroy = false
}

# 2. Configuration locals
locals {
  # Map of secret names to their variable values
  secret_map = {
    "OPENAI_API_KEY"  = var.openai_api_key_secret_id
    "GOOGLE_API_KEY"  = var.google_api_key_secret_id
    "ELASTIC_URL"     = var.elastic_url_secret_id
    "ELASTIC_API_KEY" = var.elastic_api_key_secret_id
  }
  
  # Add optional API auth token if provided
  secrets_with_auth = var.api_auth_token != "" ? merge(
    local.secret_map,
    { "API_AUTH_TOKEN" = var.api_auth_token_secret_id }
  ) : local.secret_map

  # Direct environment variables (non-sensitive)
  environment_variables = merge(
    {
      CORS_ALLOW_ORIGINS    = var.cors_allow_origins
      RATE_LIMIT_PER_MINUTE = tostring(var.rate_limit_per_minute)
      RATE_LIMIT_PER_HOUR   = tostring(var.rate_limit_per_hour)
    },
    # Direct secret variables (only if not using Secret Manager)
    var.use_secret_manager ? {} : {
      OPENAI_API_KEY  = var.openai_api_key
      GOOGLE_API_KEY  = var.google_api_key
      ELASTIC_URL     = var.elastic_url
      ELASTIC_API_KEY = var.elastic_api_key
      API_AUTH_TOKEN  = var.api_auth_token
    }
  )

  # Secret environment variables (if using Secret Manager)
  secret_environment_variables = var.use_secret_manager ? [
    for key, secret_id in local.secrets_with_auth : {
      key        = key
      project_id = var.project_id
      secret     = secret_id
      version    = "latest"
    }
  ] : []
}

# 3. Reference existing Secret Manager secrets (created by init-secrets.sh)
data "google_secret_manager_secret" "secrets" {
  for_each  = var.use_secret_manager ? local.secrets_with_auth : {}
  secret_id = each.value
  project   = var.project_id
}

# 4. IAM binding for Cloud Functions service account to access secrets
data "google_project" "project" {
  project_id = var.project_id
}

resource "google_secret_manager_secret_iam_member" "secret_accessor" {
  for_each = var.use_secret_manager ? data.google_secret_manager_secret.secrets : {}

  secret_id = each.value.secret_id
  role      = "roles/secretmanager.secretAccessor"
  member    = "serviceAccount:${data.google_project.project.number}-compute@developer.gserviceaccount.com"
}

# 5. Cloud Functions (2nd gen)
resource "google_cloudfunctions2_function" "chatbot" {
  name        = var.function_name
  location    = var.region
  description = "RAG Chatbot with Agentic Pipeline"

  build_config {
    runtime     = var.runtime
    entry_point = "main"
    source {
      storage_source {
        bucket = google_storage_bucket.function_source.name
        object = google_storage_bucket_object.function_source.name
      }
    }
  }

  service_config {
    max_instance_count    = var.max_instances
    min_instance_count    = var.min_instances
    available_memory      = var.memory
    timeout_seconds       = var.timeout
    environment_variables = local.environment_variables
    secret_environment_variables = local.secret_environment_variables

    ingress_settings               = "ALLOW_ALL"
    all_traffic_on_latest_revision = true
  }

  depends_on = [
    google_project_service.required_apis,
    google_storage_bucket.function_source,
    google_storage_bucket_object.function_source,
    google_secret_manager_secret_iam_member.secret_accessor
  ]
}

# 6. IAM binding to allow unauthenticated access
resource "google_cloudfunctions2_function_iam_member" "public_access" {
  project        = var.project_id
  location       = var.region
  cloud_function = google_cloudfunctions2_function.chatbot.name
  role           = "roles/cloudfunctions.invoker"
  member         = "allUsers"
}

# 7. Storage bucket for function source code
resource "google_storage_bucket" "function_source" {
  name     = "${var.project_id}-${var.function_name}-source"
  location = var.region

  uniform_bucket_level_access = true
  force_destroy               = true
}

# 8. Archive source code
data "archive_file" "function_source" {
  type        = "zip"
  source_dir  = abspath(var.source_dir)
  output_path = "${path.module}/.tmp/function-source.zip"
  excludes = [
    ".git",
    ".gitignore",
    "__pycache__",
    "*.pyc",
    ".env",
    "terraform",
    "*.ipynb_checkpoints",
    "data",
    ".tmp",
    "archive"
  ]
}

# 9. Upload source code to bucket
resource "google_storage_bucket_object" "function_source" {
  name   = "function-source-${data.archive_file.function_source.output_md5}.zip"
  bucket = google_storage_bucket.function_source.name
  source = data.archive_file.function_source.output_path
}

