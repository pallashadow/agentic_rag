variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP Region for Cloud Functions"
  type        = string
  default     = "us-central1"
}

variable "function_name" {
  description = "Name of the Cloud Function"
  type        = string
  default     = "chatbot-milesguo"
}

variable "runtime" {
  description = "Python runtime version"
  type        = string
  default     = "python311"
}

variable "memory" {
  description = "Memory allocation for Cloud Function (e.g., 256Mi, 512Mi)"
  type        = string
  default     = "256Mi"
}

variable "timeout" {
  description = "Timeout for Cloud Function in seconds"
  type        = number
  default     = 300
}

variable "max_instances" {
  description = "Maximum number of function instances"
  type        = number
  default     = 10
}

variable "min_instances" {
  description = "Minimum number of function instances (0 for scale-to-zero)"
  type        = number
  default     = 0
}

variable "source_dir" {
  description = "Path to the source code directory (relative to terraform directory)"
  type        = string
  default     = "../.."
}

variable "use_secret_manager" {
  description = "Whether to use Secret Manager for API keys (recommended for production)"
  type        = bool
  default     = true
}

# Secret Manager secrets (if use_secret_manager = true)
variable "openai_api_key_secret_id" {
  description = "Secret Manager secret ID for OpenAI API key"
  type        = string
  default     = "openai-api-key"
}

variable "google_api_key_secret_id" {
  description = "Secret Manager secret ID for Google API key"
  type        = string
  default     = "google-api-key"
}

variable "elastic_url_secret_id" {
  description = "Secret Manager secret ID for Elasticsearch URL"
  type        = string
  default     = "elastic-url"
}

variable "elastic_api_key_secret_id" {
  description = "Secret Manager secret ID for Elasticsearch API key"
  type        = string
  default     = "elastic-api-key"
}

variable "api_auth_token_secret_id" {
  description = "Secret Manager secret ID for API auth token (optional)"
  type        = string
  default     = "api-auth-token"
}

# Direct environment variables (if use_secret_manager = false, not recommended)
variable "openai_api_key" {
  description = "OpenAI API key (only used if use_secret_manager = false)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "google_api_key" {
  description = "Google API key (only used if use_secret_manager = false)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "elastic_url" {
  description = "Elasticsearch URL (only used if use_secret_manager = false)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "elastic_api_key" {
  description = "Elasticsearch API key (only used if use_secret_manager = false)"
  type        = string
  default     = ""
  sensitive   = true
}

variable "api_auth_token" {
  description = "API auth token (optional, only used if use_secret_manager = false)"
  type        = string
  default     = ""
  sensitive   = true
}

# Optional environment variables
variable "cors_allow_origins" {
  description = "CORS allowed origins (e.g., '*' or comma-separated list)"
  type        = string
  default     = "*"
}

variable "rate_limit_per_minute" {
  description = "Rate limit per minute"
  type        = number
  default     = 5
}

variable "rate_limit_per_hour" {
  description = "Rate limit per hour"
  type        = number
  default     = 30
}

