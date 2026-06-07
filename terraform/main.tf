terraform {
  required_version = ">= 1.0"
  backend "gcs" {
    bucket = "z-mentorai-tfstate"
    prefix = "terraform/state"
  }
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 4.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# 0. Automatically Enable GCP APIs
locals {
  gcp_services = [
    "iam.googleapis.com",
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "aiplatform.googleapis.com",
    "firestore.googleapis.com"
  ]
}

resource "google_project_service" "apis" {
  for_each           = toset(local.gcp_services)
  project            = var.project_id
  service            = each.value
  disable_on_destroy = false
}

# 1. Artifact Registry Repository
resource "google_artifact_registry_repository" "repo" {
  location      = var.region
  repository_id = var.repository_id
  description   = "Docker repository for Z-MentorAI containers"
  format        = "DOCKER"
  depends_on    = [google_project_service.apis]
}

# 2. Service Account for Orchestrator (Backend)
resource "google_service_account" "orchestrator_sa" {
  account_id   = "orchestrator-runner"
  display_name = "Service Account for Z-MentorAI Orchestrator"
  depends_on    = [google_project_service.apis]
}

# 3. Service Account for Profile Scanner Agent
resource "google_service_account" "profile_scanner_sa" {
  account_id   = "profile-scanner-runner"
  display_name = "Service Account for Z-MentorAI Profile Scanner"
  depends_on    = [google_project_service.apis]
}

# 4. Grant Firestore and Vertex AI access to runtime service accounts
resource "google_project_iam_member" "firestore_access" {
  project    = var.project_id
  role       = "roles/datastore.user"
  member     = "serviceAccount:${google_service_account.orchestrator_sa.email}"
  depends_on = [google_service_account.orchestrator_sa]
}

resource "google_project_iam_member" "vertex_access" {
  project    = var.project_id
  role       = "roles/aiplatform.user"
  member     = "serviceAccount:${google_service_account.orchestrator_sa.email}"
  depends_on = [google_service_account.orchestrator_sa]
}

resource "google_project_iam_member" "profile_scanner_firestore_access" {
  project    = var.project_id
  role       = "roles/datastore.user"
  member     = "serviceAccount:${google_service_account.profile_scanner_sa.email}"
  depends_on = [google_service_account.profile_scanner_sa]
}

# 5. Cloud Run Services (V2)

# A. Profile Scanner Agent
resource "google_cloud_run_v2_service" "profile_scanner" {
  name       = "profile-scanner"
  location   = var.region
  project    = var.project_id
  ingress    = "INGRESS_TRAFFIC_ALL"
  depends_on = [
    google_project_service.apis,
    google_project_iam_member.profile_scanner_firestore_access
  ]

  template {
    service_account = google_service_account.profile_scanner_sa.email
    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.repo.name}/${var.profile_scanner_image}"
      ports {
        container_port = 8080
      }
      env {
        name  = "USE_FIRESTORE"
        value = "true"
      }
      env {
        name  = "FIRESTORE_DATABASE"
        value = "(default)"
      }
      env {
        name  = "HOLLAND_COLLECTION_NAME"
        value = "profile_scanner_holland_assessments"
      }
    }
  }
}

# B. Market Scout Agent
resource "google_cloud_run_v2_service" "market_scout" {
  name       = "market-scout"
  location   = var.region
  project    = var.project_id
  ingress    = "INGRESS_TRAFFIC_ALL"
  depends_on = [google_project_service.apis]

  template {
    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.repo.name}/${var.market_scout_image}"
      ports {
        container_port = 8080
      }
    }
  }
}

# C. Academic Architect Agent
resource "google_cloud_run_v2_service" "academic_architect" {
  name       = "academic-architect"
  location   = var.region
  project    = var.project_id
  ingress    = "INGRESS_TRAFFIC_ALL"
  depends_on = [google_project_service.apis]

  template {
    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.repo.name}/${var.academic_architect_image}"
      ports {
        container_port = 8080
      }
    }
  }
}

# D. MCP Server (orchestrates communication with scanner, scout, and architect)
resource "google_cloud_run_v2_service" "mcp_server" {
  name       = "mcp-server"
  location   = var.region
  project    = var.project_id
  ingress    = "INGRESS_TRAFFIC_ALL"
  depends_on = [google_project_service.apis]

  template {
    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.repo.name}/${var.mcp_server_image}"
      ports {
        container_port = 8080
      }
      env {
        name  = "PROFILE_SCANNER_URL"
        value = google_cloud_run_v2_service.profile_scanner.uri
      }
      env {
        name  = "MARKET_SCOUT_URL"
        value = google_cloud_run_v2_service.market_scout.uri
      }
      env {
        name  = "ACADEMIC_ARCHITECT_URL"
        value = google_cloud_run_v2_service.academic_architect.uri
      }
    }
  }
}

# E. Orchestrator Backend & Frontend host
resource "google_cloud_run_v2_service" "orchestrator" {
  name       = "orchestrator"
  location   = var.region
  project    = var.project_id
  ingress    = "INGRESS_TRAFFIC_ALL"
  depends_on = [
    google_project_service.apis,
    google_project_iam_member.firestore_access,
    google_project_iam_member.vertex_access
  ]

  template {
    service_account = google_service_account.orchestrator_sa.email
    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.repo.name}/${var.orchestrator_image}"
      ports {
        container_port = 8080
      }
      env {
        name  = "MCP_SERVER_URL"
        value = "${google_cloud_run_v2_service.mcp_server.uri}/sse"
      }
      env {
        name  = "USE_FIRESTORE"
        value = "true"
      }
      env {
        name  = "USE_VERTEX_AI"
        value = "true"
      }
      env {
        name  = "GOOGLE_CLIENT_ID"
        value = var.google_client_id
      }
      env {
        name  = "FIRESTORE_DATABASE"
        value = "(default)"
      }
    }
  }
}

# 6. Make all Cloud Run Services Publicly Accessible (V2 IAM resources)
resource "google_cloud_run_v2_service_iam_member" "public_profile_scanner" {
  project  = google_cloud_run_v2_service.profile_scanner.project
  location = google_cloud_run_v2_service.profile_scanner.location
  name     = google_cloud_run_v2_service.profile_scanner.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_v2_service_iam_member" "public_market_scout" {
  project  = google_cloud_run_v2_service.market_scout.project
  location = google_cloud_run_v2_service.market_scout.location
  name     = google_cloud_run_v2_service.market_scout.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_v2_service_iam_member" "public_academic_architect" {
  project  = google_cloud_run_v2_service.academic_architect.project
  location = google_cloud_run_v2_service.academic_architect.location
  name     = google_cloud_run_v2_service.academic_architect.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_v2_service_iam_member" "public_mcp_server" {
  project  = google_cloud_run_v2_service.mcp_server.project
  location = google_cloud_run_v2_service.mcp_server.location
  name     = google_cloud_run_v2_service.mcp_server.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_v2_service_iam_member" "public_orchestrator" {
  project  = google_cloud_run_v2_service.orchestrator.project
  location = google_cloud_run_v2_service.orchestrator.location
  name     = google_cloud_run_v2_service.orchestrator.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
