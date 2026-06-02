terraform {
  required_version = ">= 1.0"
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

# 3. Grant Firestore and Vertex AI access to Orchestrator SA
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

# 4. Cloud Run Services

# A. Profile Scanner Agent
resource "google_cloud_run_service" "profile_scanner" {
  name       = "profile-scanner"
  location   = var.region
  project    = var.project_id
  depends_on = [google_project_service.apis]

  template {
    spec {
      containers {
        image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.repo.name}/${var.profile_scanner_image}"
        ports {
          container_port = 8080
        }
      }
    }
  }
  traffic {
    percent         = 100
    latest_revision = true
  }
}

# B. Market Scout Agent
resource "google_cloud_run_service" "market_scout" {
  name       = "market-scout"
  location   = var.region
  project    = var.project_id
  depends_on = [google_project_service.apis]

  template {
    spec {
      containers {
        image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.repo.name}/${var.market_scout_image}"
        ports {
          container_port = 8080
        }
      }
    }
  }
  traffic {
    percent         = 100
    latest_revision = true
  }
}

# C. Academic Architect Agent
resource "google_cloud_run_service" "academic_architect" {
  name       = "academic-architect"
  location   = var.region
  project    = var.project_id
  depends_on = [google_project_service.apis]

  template {
    spec {
      containers {
        image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.repo.name}/${var.academic_architect_image}"
        ports {
          container_port = 8080
        }
      }
    }
  }
  traffic {
    percent         = 100
    latest_revision = true
  }
}

# D. MCP Server (orchestrates communication with scanner, scout, and architect)
resource "google_cloud_run_service" "mcp_server" {
  name       = "mcp-server"
  location   = var.region
  project    = var.project_id
  depends_on = [google_project_service.apis]

  template {
    spec {
      containers {
        image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.repo.name}/${var.mcp_server_image}"
        ports {
          container_port = 8080
        }
        env {
          name  = "PROFILE_SCANNER_URL"
          value = google_cloud_run_service.profile_scanner.status[0].url
        }
        env {
          name  = "MARKET_SCOUT_URL"
          value = google_cloud_run_service.market_scout.status[0].url
        }
        env {
          name  = "ACADEMIC_ARCHITECT_URL"
          value = google_cloud_run_service.academic_architect.status[0].url
        }
      }
    }
  }
  traffic {
    percent         = 100
    latest_revision = true
  }
}

# E. Orchestrator Backend & Frontend host
resource "google_cloud_run_service" "orchestrator" {
  name       = "orchestrator"
  location   = var.region
  project    = var.project_id
  depends_on = [google_project_service.apis]

  template {
    spec {
      service_account_name = google_service_account.orchestrator_sa.email
      containers {
        image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.repo.name}/${var.orchestrator_image}"
        ports {
          container_port = 8080
        }
        env {
          name  = "MCP_SERVER_URL"
          value = "${google_cloud_run_service.mcp_server.status[0].url}/sse"
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
          value = "database"
        }
      }
    }
  }
  traffic {
    percent         = 100
    latest_revision = true
  }
}

# 5. Make all Cloud Run Services Publicly Accessible
resource "google_cloud_run_service_iam_member" "public_profile_scanner" {
  service  = google_cloud_run_service.profile_scanner.name
  location = google_cloud_run_service.profile_scanner.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_service_iam_member" "public_market_scout" {
  service  = google_cloud_run_service.market_scout.name
  location = google_cloud_run_service.market_scout.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_service_iam_member" "public_academic_architect" {
  service  = google_cloud_run_service.academic_architect.name
  location = google_cloud_run_service.academic_architect.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_service_iam_member" "public_mcp_server" {
  service  = google_cloud_run_service.mcp_server.name
  location = google_cloud_run_service.mcp_server.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}

resource "google_cloud_run_service_iam_member" "public_orchestrator" {
  service  = google_cloud_run_service.orchestrator.name
  location = google_cloud_run_service.orchestrator.location
  role     = "roles/run.invoker"
  member   = "allUsers"
}
