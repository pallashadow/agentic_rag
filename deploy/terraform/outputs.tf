output "function_name" {
  description = "Name of the Cloud Function"
  value       = google_cloudfunctions2_function.chatbot.name
}

output "function_url" {
  description = "URL of the Cloud Function"
  value       = google_cloudfunctions2_function.chatbot.service_config[0].uri
}

output "function_location" {
  description = "Location of the Cloud Function"
  value       = google_cloudfunctions2_function.chatbot.location
}

output "source_bucket" {
  description = "GCS bucket name for function source code"
  value       = google_storage_bucket.function_source.name
}

output "secret_names" {
  description = "Secret Manager secret names (if using Secret Manager)"
  value       = var.use_secret_manager ? { for k, v in data.google_secret_manager_secret.secrets : k => v.secret_id } : null
  sensitive   = false
}

