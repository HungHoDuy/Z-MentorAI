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
