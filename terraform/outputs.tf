output "app_url" {
  value       = google_cloud_run_v2_service.orchestrator.uri
  description = "The public URL of the Z-MentorAI application."
}

output "mcp_server_url" {
  value       = google_cloud_run_v2_service.mcp_server.uri
  description = "The public URL of the MCP Server."
}
