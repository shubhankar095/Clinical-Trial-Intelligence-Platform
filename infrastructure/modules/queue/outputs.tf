output "queue_id" {
  description = "ID of the primary SQS queue. For SQS, this value is the queue URL."
  value       = aws_sqs_queue.this.id
}

output "queue_url" {
  description = "URL of the primary SQS queue."
  value       = aws_sqs_queue.this.url
}

output "queue_arn" {
  description = "ARN of the primary SQS queue."
  value       = aws_sqs_queue.this.arn
}

output "queue_name" {
  description = "Name of the primary SQS queue."
  value       = aws_sqs_queue.this.name
}

output "dlq_id" {
  description = "ID of the dead-letter queue. For SQS, this value is the queue URL."
  value       = aws_sqs_queue.dlq.id
}

output "dlq_url" {
  description = "URL of the dead-letter queue."
  value       = aws_sqs_queue.dlq.url
}

output "dlq_arn" {
  description = "ARN of the dead-letter queue."
  value       = aws_sqs_queue.dlq.arn
}

output "dlq_name" {
  description = "Name of the dead-letter queue."
  value       = aws_sqs_queue.dlq.name
}