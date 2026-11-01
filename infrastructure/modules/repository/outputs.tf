output "repository_id" {
  description = "Registry ID and repository name."
  value       = aws_ecr_repository.this.id
}

output "repository_name" {
  description = "Name of the ECR repository."
  value       = aws_ecr_repository.this.name
}

output "repository_arn" {
  description = "ARN of the ECR repository."
  value       = aws_ecr_repository.this.arn
}

output "repository_url" {
  description = "URL of the ECR repository."
  value       = aws_ecr_repository.this.repository_url
}

output "registry_id" {
  description = "Registry ID containing the ECR repository."
  value       = aws_ecr_repository.this.registry_id
}