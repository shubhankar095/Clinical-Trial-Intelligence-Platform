output "topic_id" {
  description = "ID of the SNS alert topic."
  value       = aws_sns_topic.this.id
}

output "topic_arn" {
  description = "ARN of the SNS alert topic."
  value       = aws_sns_topic.this.arn
}

output "topic_name" {
  description = "Name of the SNS alert topic."
  value       = aws_sns_topic.this.name
}

output "email_subscription_arn" {
  description = "ARN of the email subscription."
  value       = aws_sns_topic_subscription.email.arn
}