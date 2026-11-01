output "task_definition_id" {
  description = "ID of the ECS task definition."
  value       = aws_ecs_task_definition.this.id
}

output "task_definition_arn" {
  description = "Full ARN of the ECS task definition revision."
  value       = aws_ecs_task_definition.this.arn
}

output "task_definition_family" {
  description = "Family name of the ECS task definition."
  value       = aws_ecs_task_definition.this.family
}

output "task_definition_revision" {
  description = "Revision number of the ECS task definition."
  value       = aws_ecs_task_definition.this.revision
}

output "service_id" {
  description = "ID of the ECS service."
  value       = aws_ecs_service.this.id
}

output "service_name" {
  description = "Name of the ECS service."
  value       = aws_ecs_service.this.name
}

output "cluster_id" {
  description = "ID or ARN of the ECS cluster used by the service."
  value       = aws_ecs_service.this.cluster
}