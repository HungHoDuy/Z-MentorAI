variable "project_id" {
  type        = string
  description = "The GCP Project ID to deploy resources to."
  default     = "z-mentorai"
}

variable "region" {
  type        = string
  description = "GCP Region for Cloud Run and Artifact Registry deployment."
  default     = "asia-southeast1" # Singapore
}

variable "repository_id" {
  type        = string
  description = "The ID of the Artifact Registry repository for container images."
  default     = "z-mentor-repo"
}

variable "google_client_id" {
  type        = string
  description = "The Google OAuth Client ID used by the orchestrator for user logins."
  default     = "1048615702319-fjmfv9it0cor8br7mfsbkfjdkv1vpnk3.apps.googleusercontent.com"
}

variable "orchestrator_image" {
  type        = string
  description = "Docker image for the orchestrator service."
  default     = "orchestrator:latest"
}

variable "mcp_server_image" {
  type        = string
  description = "Docker image for the MCP server service."
  default     = "mcp-server:latest"
}

variable "profile_scanner_image" {
  type        = string
  description = "Docker image for the profile scanner agent."
  default     = "profile-scanner:latest"
}

variable "market_scout_image" {
  type        = string
  description = "Docker image for the market scout agent."
  default     = "market-scout:latest"
}

variable "academic_architect_image" {
  type        = string
  description = "Docker image for the academic architect agent."
  default     = "academic-architect:latest"
}

variable "profile_scanner_cv_bucket_name" {
  type        = string
  description = "Private GCS bucket for Profile Scanner CV uploads."
  default     = "z-mentorai-profile-scanner-cv"
}

variable "document_ai_location" {
  type        = string
  description = "Document AI processor location used by Profile Scanner OCR fallback."
  default     = "asia-southeast1"
}
