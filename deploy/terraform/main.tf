terraform {
  required_version = ">= 1.5"
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 5.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.location
}

# APIs the Tier-1 agent needs (all billed to the user's own project).
locals {
  services = [
    "aiplatform.googleapis.com",
    "storage.googleapis.com",
    "firestore.googleapis.com",
    "cloudscheduler.googleapis.com",
    "run.googleapis.com",
  ]
}

resource "google_project_service" "enabled" {
  for_each           = toset(local.services)
  service            = each.value
  disable_on_destroy = false
}

# Source docs + compiled packs live here, in the user's project.
resource "google_storage_bucket" "docs" {
  name                        = var.bucket_name
  location                    = var.location
  uniform_bucket_level_access = true
  force_destroy               = false
  versioning {
    enabled = true
  }
  depends_on = [google_project_service.enabled]
}

# Baselines / findings store. A project may only have one (default) database — set
# create_firestore=false if it already exists (otherwise apply fails on the pre-existing DB).
resource "google_firestore_database" "db" {
  count       = var.create_firestore ? 1 : 0
  name        = "(default)"
  location_id = var.location
  type        = "FIRESTORE_NATIVE"
  depends_on  = [google_project_service.enabled]
}

# Least-privilege identity the agent runs as.
resource "google_service_account" "agent" {
  account_id   = var.service_account_id
  display_name = "ToS/Compliance Agent"
  depends_on   = [google_project_service.enabled]
}

resource "google_project_iam_member" "aiplatform_user" {
  project = var.project_id
  role    = "roles/aiplatform.user"
  member  = "serviceAccount:${google_service_account.agent.email}"
}

resource "google_project_iam_member" "datastore_user" {
  project = var.project_id
  role    = "roles/datastore.user"
  member  = "serviceAccount:${google_service_account.agent.email}"
}

# Bucket-scoped object admin (not project-wide storage admin).
resource "google_storage_bucket_iam_member" "bucket_object_admin" {
  bucket = google_storage_bucket.docs.name
  role   = "roles/storage.objectAdmin"
  member = "serviceAccount:${google_service_account.agent.email}"
}
