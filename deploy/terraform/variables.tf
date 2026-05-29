variable "project_id" {
  type        = string
  description = "Your Google Cloud project ID (everything is provisioned here; single-tenant)."
}

variable "location" {
  type        = string
  default     = "us-central1"
  description = "Region for Vertex AI, the GCS bucket, and Firestore."
}

variable "bucket_name" {
  type        = string
  description = "Globally-unique GCS bucket name for source docs + compiled packs."
}

variable "service_account_id" {
  type        = string
  default     = "compliance-agent"
  description = "ID for the least-privilege service account the agent runs as."
}

variable "create_firestore" {
  type        = bool
  default     = true
  description = "Create the (default) Firestore database. Set false if the project already has one (a project can only have one (default) DB, in one mode/location)."
}
