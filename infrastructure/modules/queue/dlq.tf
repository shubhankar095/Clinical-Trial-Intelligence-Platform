resource "aws_sqs_queue" "dlq" {
  name = var.dlq_name

  message_retention_seconds = var.dlq_message_retention_seconds

  tags = merge(
    var.tags,
    {
      Name = var.dlq_name
    }
  )
}