output "vpc_id" {
  value = module.network.vpc_id
}

output "public_subnet_ids" {
  value = module.network.public_subnet_ids
}

output "public_route_table_id" {
  value = module.network.public_route_table_id
}

output "raw_bucket_name" {
  value = module.raw_bucket.bucket_name
}

output "raw_bucket_arn" {
  value = module.raw_bucket.bucket_arn
}

output "canonical_bucket_name" {
  value = module.canonical_bucket.bucket_name
}

output "canonical_bucket_arn" {
  value = module.canonical_bucket.bucket_arn
}

output "ecs_cluster_id" {
  value = module.ecs_cluster.cluster_id
}

output "ecs_cluster_arn" {
  value = module.ecs_cluster.cluster_arn
}

output "ecs_cluster_name" {
  value = module.ecs_cluster.cluster_name
}

output "opensearch_collection_id" {
  description = "ID of the shared OpenSearch Serverless collection."
  value       = module.opensearch_serverless.collection_id
}

output "opensearch_collection_name" {
  description = "Name of the shared OpenSearch Serverless collection."
  value       = module.opensearch_serverless.collection_name
}

output "opensearch_collection_arn" {
  description = "ARN of the shared OpenSearch Serverless collection."
  value       = module.opensearch_serverless.collection_arn
}

output "opensearch_collection_endpoint" {
  description = "Endpoint of the shared OpenSearch Serverless collection."
  value       = module.opensearch_serverless.collection_endpoint
}

output "opensearch_dashboard_endpoint" {
  description = "Dashboards endpoint of the shared OpenSearch Serverless collection."
  value       = module.opensearch_serverless.dashboard_endpoint
}

output "opensearch_collection_group_id" {
  description = "ID of the shared OpenSearch Serverless collection group."
  value       = module.opensearch_serverless.collection_group_id
}

output "opensearch_collection_group_name" {
  description = "Name of the shared OpenSearch Serverless collection group."
  value       = module.opensearch_serverless.collection_group_name
}

output "opensearch_collection_group_arn" {
  description = "ARN of the shared OpenSearch Serverless collection group."
  value       = module.opensearch_serverless.collection_group_arn
}