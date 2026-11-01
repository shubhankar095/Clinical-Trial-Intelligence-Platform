output "collection_id" {
  description = "Unique identifier of the OpenSearch Serverless collection."
  value       = aws_opensearchserverless_collection.this.id
}

output "collection_name" {
  description = "Name of the OpenSearch Serverless collection."
  value       = aws_opensearchserverless_collection.this.name
}

output "collection_arn" {
  description = "ARN of the OpenSearch Serverless collection."
  value       = aws_opensearchserverless_collection.this.arn
}

output "collection_endpoint" {
  description = "HTTPS endpoint of the OpenSearch Serverless collection."
  value       = aws_opensearchserverless_collection.this.collection_endpoint
}

output "dashboard_endpoint" {
  description = "OpenSearch Dashboards endpoint for the collection."
  value       = aws_opensearchserverless_collection.this.dashboard_endpoint
}

output "encryption_policy_name" {
  description = "Name of the collection encryption policy."
  value       = aws_opensearchserverless_security_policy.encryption.name
}

output "network_policy_name" {
  description = "Name of the collection network policy."
  value       = aws_opensearchserverless_security_policy.network.name
}


output "collection_group_id" {
  description = "Unique identifier of the OpenSearch Serverless collection group."
  value       = aws_opensearchserverless_collection_group.this.id
}

output "collection_group_arn" {
  description = "ARN of the OpenSearch Serverless collection group."
  value       = aws_opensearchserverless_collection_group.this.arn
}

output "collection_group_name" {
  description = "Name of the OpenSearch Serverless collection group."
  value       = aws_opensearchserverless_collection_group.this.name
}