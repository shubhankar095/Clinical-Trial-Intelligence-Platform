output "log_group_id" {
  description = "ID of the CloudWatch log group."
  value       = aws_cloudwatch_log_group.this.id
}

output "log_group_name" {
  description = "Name of the CloudWatch log group."
  value       = aws_cloudwatch_log_group.this.name
}

output "log_group_arn" {
  description = "ARN of the CloudWatch log group."
  value       = aws_cloudwatch_log_group.this.arn
}