locals {
  project_prefix = var.project_name

  extraction_queue_name = (
    "${var.project_name}-extraction-${var.environment}"
  )

  extraction_dlq_name = (
    "${var.project_name}-extraction-dlq-${var.environment}"
  )

  processing_registry_table_name = (
    "${var.project_name}-extraction-processing-${var.environment}"
  )

  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "Terraform"
    Service     = "Extraction"
  }
}