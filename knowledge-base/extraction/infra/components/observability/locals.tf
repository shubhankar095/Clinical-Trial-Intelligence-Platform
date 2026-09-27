locals {
  project_prefix = var.project_name

  extraction_metric_namespace = (
    "${var.project_name}/Extraction/${var.environment}"
  )

  common_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "Terraform"
    Service     = "Extraction"
  }
}