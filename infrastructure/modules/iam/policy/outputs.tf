output "policy_id" {
  description = "ID of the customer-managed IAM policy."
  value       = aws_iam_policy.this.id
}

output "policy_name" {
  description = "Name of the customer-managed IAM policy."
  value       = aws_iam_policy.this.name
}

output "policy_arn" {
  description = "ARN of the customer-managed IAM policy."
  value       = aws_iam_policy.this.arn
}
