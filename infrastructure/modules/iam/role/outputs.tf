output "role_id" {
  description = "ID of the IAM role."
  value       = aws_iam_role.this.id
}

output "role_name" {
  description = "Name of the IAM role."
  value       = aws_iam_role.this.name
}

output "role_arn" {
  description = "ARN of the IAM role."
  value       = aws_iam_role.this.arn
}

output "attached_policy_arns" {
  description = "Managed IAM policy ARNs attached to the IAM role, keyed by attachment identifier."
  value       = var.policy_arns
}