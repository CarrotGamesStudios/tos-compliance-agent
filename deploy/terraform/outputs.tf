output "bucket" {
  value       = google_storage_bucket.docs.name
  description = "GCS bucket holding source docs + compiled packs."
}

output "service_account_email" {
  value       = google_service_account.agent.email
  description = "Run the agent / Cloud Scheduler job as this identity."
}

output "project_id" {
  value = var.project_id
}

output "location" {
  value = var.location
}
