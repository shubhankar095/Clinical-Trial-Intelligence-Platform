output "ingestion_queue_url" {
  value = module.ingestion_queue.queue_url
}

output "ingestion_queue_arn" {
  value = module.ingestion_queue.queue_arn
}

output "ingestion_dlq_arn" {
  value = module.ingestion_queue.dlq_arn
}

output "canonical_bucket" {
  value = local.platform.canonical_bucket_name
}

output "ecs_cluster" {
  value = local.platform.ecs_cluster_name
}

output "ecr_repository_url" {
  value = module.ingestion_repository.repository_url
}

output "vpc_id" {
  value = local.platform.vpc_id
}

output "subnet_ids" {
  value = local.platform.public_subnet_ids
}

output "security_group_id" {
  value = module.ingestion_security_group.security_group_id
}

output "ecs_service_name" {
  value = module.ingestion_worker.service_name
}

output "cloudwatch_log_group" {
  value = module.ingestion_logs.log_group_name
}

output "ingestion_image_uri" {
  value = "${module.ingestion_repository.repository_url}:${var.image_tag}"
}

output "cloudwatch_dashboard_name" {
  value = module.ingestion_monitoring.dashboard_name
}

output "processing_registry_table" {
  value = module.ingestion_registry.table_name
}

output "task_role_arn" {
  description = "ARN of the IAM role used by the running Ingestion application."
  value       = module.ingestion_task_role.role_arn
}

output "execution_role_arn" {
  description = "ARN of the IAM role used by ECS to start the Ingestion task."
  value       = module.ingestion_execution_role.role_arn
}

output "opensearch_collection_name" {
  description = "Name of the shared OpenSearch Serverless collection."
  value       = local.platform.opensearch_collection_name
}

output "opensearch_collection_arn" {
  description = "ARN of the shared OpenSearch Serverless collection."
  value       = local.platform.opensearch_collection_arn
}

output "opensearch_collection_endpoint" {
  description = "Endpoint of the shared OpenSearch Serverless collection."
  value       = local.platform.opensearch_collection_endpoint
}

output "opensearch_access_policy_name" {
  description = "Name of the Ingestion OpenSearch Serverless data-access policy."
  value       = aws_opensearchserverless_access_policy.ingestion.name
}