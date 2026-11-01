output "dashboard_name" {
  description = "Name of the CloudWatch monitoring dashboard."
  value       = aws_cloudwatch_dashboard.this.dashboard_name
}

output "metric_namespace" {
  description = "CloudWatch custom metric namespace used by log metric filters."
  value       = var.metric_namespace
}

output "dlq_alarm_arn" {
  description = "ARN of the DLQ messages alarm."
  value       = aws_cloudwatch_metric_alarm.dlq_messages.arn
}

output "oldest_message_alarm_arn" {
  description = "ARN of the oldest-message-age alarm."
  value       = aws_cloudwatch_metric_alarm.oldest_message_age.arn
}

output "processing_failures_alarm_arn" {
  description = "ARN of the processing-failures alarm."
  value       = aws_cloudwatch_metric_alarm.processing_failures.arn
}