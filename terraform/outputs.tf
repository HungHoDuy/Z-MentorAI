output "app_url" {
  value       = google_cloud_run_service.orchestrator.status[0].url
  description = "The public URL of the Z-MentorAI application."
}

output "mcp_server_url" {
  value       = google_cloud_run_service.mcp_server.status[0].url
  description = "The public URL of the MCP Server."
}
