output "extraction_queue_url" {
  value = module.extraction_queue.queue_url
}

output "extraction_queue_arn" {
  value = module.extraction_queue.queue_arn
}

output "extraction_dlq_arn" {
  value = module.extraction_queue.dlq_arn
}

output "raw_bucket" {
  value = local.platform.raw_bucket_name
}

output "canonical_bucket" {
  value = local.platform.canonical_bucket_name
}

output "ecs_cluster" {
  value = local.platform.ecs_cluster_name
}

output "ecr_repository_url" {
  value = module.extraction_repository.repository_url
}

output "vpc_id" {
  value = local.platform.vpc_id
}

output "subnet_ids" {
  value = local.platform.public_subnet_ids
}

output "security_group_id" {
  value = module.extraction_security_group.security_group_id
}

output "ecs_service_name" {
  value = module.extraction_worker.service_name
}

output "cloudwatch_log_group" {
  value = module.extraction_logs.log_group_name
}

output "extraction_image_uri" {
  value = "${module.extraction_repository.repository_url}:${var.image_tag}"
}

output "cloudwatch_dashboard_name" {
  value = module.extraction_monitoring.dashboard_name
}

output "processing_registry_table" {
  value = module.extraction_registry.table_name
}
