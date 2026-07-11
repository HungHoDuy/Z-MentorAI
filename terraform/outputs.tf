output "app_url" {
  value       = google_cloud_run_v2_service.orchestrator.uri
  description = "The public URL of the Z-MentorAI application."
}

output "mcp_server_url" {
  value       = google_cloud_run_v2_service.mcp_server.uri
  description = "The public URL of the MCP Server."
}

output "profile_scanner_url" {
  value       = google_cloud_run_v2_service.profile_scanner.uri
  description = "The public URL of the Profile Scanner agent."
}

output "profile_scanner_cv_bucket" {
  value       = google_storage_bucket.profile_scanner_cv_bucket.name
  description = "The private GCS bucket used for Profile Scanner CV uploads."
}

output "profile_scanner_document_ai_processor" {
  value       = google_document_ai_processor.profile_scanner_cv_ocr.id
  description = "The Document AI OCR processor used by Profile Scanner PDF fallback extraction."
}

output "profile_scanner_benchmark_cache_ttl_field" {
  value       = google_firestore_field.profile_scanner_benchmark_cache_ttl.name
  description = "Firestore TTL field used by the Profile Scanner dynamic benchmark cache."
}
