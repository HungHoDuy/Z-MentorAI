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
    "firestore.googleapis.com",
    "storage.googleapis.com",
    "documentai.googleapis.com"
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
  depends_on   = [google_project_service.apis]
}

# 3. Service Account for Profile Scanner Agent
resource "google_service_account" "profile_scanner_sa" {
  account_id   = "profile-scanner-runner"
  display_name = "Service Account for Z-MentorAI Profile Scanner"
  depends_on   = [google_project_service.apis]
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

resource "google_project_iam_member" "profile_scanner_vertex_access" {
  project    = var.project_id
  role       = "roles/aiplatform.user"
  member     = "serviceAccount:${google_service_account.profile_scanner_sa.email}"
  depends_on = [google_service_account.profile_scanner_sa]
}

resource "google_storage_bucket" "profile_scanner_cv_bucket" {
  name                        = var.profile_scanner_cv_bucket_name
  location                    = var.region
  project                     = var.project_id
  uniform_bucket_level_access = true
  public_access_prevention    = "enforced"
  depends_on                  = [google_project_service.apis]

  versioning {
    enabled = true
  }

  lifecycle_rule {
    condition {
      days_since_noncurrent_time = 30
    }
    action {
      type = "Delete"
    }
  }

}

resource "google_storage_bucket_iam_member" "profile_scanner_cv_bucket_object_user" {
  bucket = google_storage_bucket.profile_scanner_cv_bucket.name
  role   = "roles/storage.objectUser"
  member = "serviceAccount:${google_service_account.profile_scanner_sa.email}"
}

resource "google_document_ai_processor" "profile_scanner_cv_ocr" {
  project      = var.project_id
  location     = var.document_ai_location
  display_name = "profile-scanner-cv-ocr"
  type         = "OCR_PROCESSOR"

  depends_on = [google_project_service.apis]
}

resource "google_project_iam_member" "profile_scanner_document_ai_access" {
  project    = var.project_id
  role       = "roles/documentai.apiUser"
  member     = "serviceAccount:${google_service_account.profile_scanner_sa.email}"
  depends_on = [google_service_account.profile_scanner_sa]
}

# Firestore composite index required by:
# profile_scanner_holland_assessments.where(user_id == X).order_by(created_at desc).limit(1)
resource "google_firestore_index" "holland_assessments_by_user_created_at" {
  project     = var.project_id
  database    = "(default)"
  collection  = "profile_scanner_holland_assessments"
  query_scope = "COLLECTION"

  fields {
    field_path = "user_id"
    order      = "ASCENDING"
  }

  fields {
    field_path = "created_at"
    order      = "DESCENDING"
  }

  depends_on = [google_project_service.apis]
}

# Firestore composite index required by:
# profile_scanner_assessments.where(user_id == X).where(assessment_type == Y).order_by(created_at desc).limit(1)
resource "google_firestore_index" "profile_scanner_assessments_by_user_type_created_at" {
  project     = var.project_id
  database    = "(default)"
  collection  = "profile_scanner_assessments"
  query_scope = "COLLECTION"

  fields {
    field_path = "user_id"
    order      = "ASCENDING"
  }

  fields {
    field_path = "assessment_type"
    order      = "ASCENDING"
  }

  fields {
    field_path = "created_at"
    order      = "DESCENDING"
  }

  depends_on = [google_project_service.apis]
}

# Latest CV lookup when the user supplies a target role after the upload turn.
resource "google_firestore_index" "profile_scanner_cv_documents_by_user_uploaded_at" {
  project     = var.project_id
  database    = "(default)"
  collection  = "profile_scanner_cv_documents"
  query_scope = "COLLECTION"

  fields {
    field_path = "user_id"
    order      = "ASCENDING"
  }

  fields {
    field_path = "uploaded_at"
    order      = "DESCENDING"
  }

  depends_on = [google_project_service.apis]
}

# Expired benchmark cache pointers are removed automatically. Immutable benchmark
# snapshots remain available for score reproducibility and audit.
resource "google_firestore_field" "profile_scanner_benchmark_cache_ttl" {
  project    = var.project_id
  database   = "(default)"
  collection = "profile_scanner_benchmark_cache"
  field      = "expires_at"

  ttl_config {}
  index_config {}

  depends_on = [google_project_service.apis]
}

# 5. Cloud Run Services (V2)

# A. Profile Scanner Agent
resource "google_cloud_run_v2_service" "profile_scanner" {
  name     = "profile-scanner"
  location = var.region
  project  = var.project_id
  ingress  = "INGRESS_TRAFFIC_ALL"
  depends_on = [
    google_project_service.apis,
    google_project_iam_member.profile_scanner_firestore_access,
    google_project_iam_member.profile_scanner_vertex_access,
    google_storage_bucket_iam_member.profile_scanner_cv_bucket_object_user,
    google_project_iam_member.profile_scanner_document_ai_access,
    google_document_ai_processor.profile_scanner_cv_ocr
  ]

  template {
    timeout         = "600s"
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
      env {
        name  = "ASSESSMENTS_COLLECTION_NAME"
        value = "profile_scanner_assessments"
      }
      env {
        name  = "CV_STORAGE_BUCKET"
        value = google_storage_bucket.profile_scanner_cv_bucket.name
      }
      env {
        name  = "CV_DOCUMENTS_COLLECTION"
        value = "profile_scanner_cv_documents"
      }
      env {
        name  = "PROFILE_SCANNER_CV_EXTRACTIONS_COLLECTION"
        value = "profile_scanner_cv_extractions"
      }
      env {
        name  = "PROFILE_SCANNER_PROFILES_COLLECTION"
        value = "profile_scanner_profiles"
      }
      env {
        name  = "PROFILE_SCANNER_PROFILE_VERSIONS_COLLECTION"
        value = "profile_scanner_profile_versions"
      }
      env {
        name  = "PROFILE_SCANNER_ALIGNMENT_COLLECTION"
        value = "profile_scanner_alignment_results"
      }
      env {
        name  = "CV_MAX_FILE_SIZE_BYTES"
        value = "10485760"
      }
      env {
        name  = "GOOGLE_CLOUD_PROJECT"
        value = var.project_id
      }
      env {
        name  = "DOCUMENT_AI_LOCATION"
        value = var.document_ai_location
      }
      env {
        name  = "DOCUMENT_AI_PROCESSOR_NAME"
        value = google_document_ai_processor.profile_scanner_cv_ocr.id
      }
      env {
        name  = "USE_VERTEX_AI"
        value = "true"
      }
      env {
        name  = "VERTEX_AI_LOCATION"
        value = var.region
      }
      env {
        name  = "PROFILE_AI_EXTRACTION_ENABLED"
        value = "true"
      }
      env {
        name  = "PROFILE_AI_MODEL_NAME"
        value = "gemini-2.5-flash"
      }
      env {
        name  = "DYNAMIC_BENCHMARK_ENABLED"
        value = "true"
      }
      env {
        name  = "BENCHMARK_SNAPSHOTS_COLLECTION"
        value = "profile_scanner_benchmark_snapshots"
      }
      env {
        name  = "BENCHMARK_CACHE_COLLECTION"
        value = "profile_scanner_benchmark_cache"
      }
      env {
        name  = "BENCHMARK_JOB_FACTS_COLLECTION"
        value = "trend_job_facts_v2"
      }
      env {
        name  = "BENCHMARK_EMBEDDING_COLLECTION"
        value = "job_mapping_embedding"
      }
      env {
        name  = "BENCHMARK_EMBEDDING_MODEL"
        value = "text-multilingual-embedding-002"
      }
      env {
        name  = "BENCHMARK_EMBEDDING_LOCATION"
        value = "us-central1"
      }
      env {
        name  = "BENCHMARK_MARKET_WINDOW_DAYS"
        value = "365"
      }
      env {
        name  = "BENCHMARK_CACHE_DAYS"
        value = "7"
      }
      env {
        name  = "BENCHMARK_DEFAULT_LOCATION"
        value = "vietnam"
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
    scaling {
      min_instance_count = 1
    }
    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/${google_artifact_registry_repository.repo.name}/${var.academic_architect_image}"
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
    timeout = "600s"
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
        name  = "PROFILE_SCANNER_SCAN_TIMEOUT_SECONDS"
        value = "540"
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
  name     = "orchestrator"
  location = var.region
  project  = var.project_id
  ingress  = "INGRESS_TRAFFIC_ALL"
  depends_on = [
    google_project_service.apis,
    google_project_iam_member.firestore_access,
    google_project_iam_member.vertex_access
  ]

  template {
    timeout         = "600s"
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
        name  = "PROFILE_SCANNER_URL"
        value = google_cloud_run_v2_service.profile_scanner.uri
      }
      env {
        name  = "ACADEMIC_ARCHITECT_URL"
        value = google_cloud_run_v2_service.academic_architect.uri
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
