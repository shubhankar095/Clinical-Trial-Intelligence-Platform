data "aws_caller_identity" "current" {}

resource "aws_sqs_queue" "extraction_dlq" {
  name                      = local.extraction_dlq_name
  message_retention_seconds = 1209600
  tags = merge(
    local.common_tags,
    {
      Name = local.extraction_dlq_name
    }
  )
}

resource "aws_sqs_queue" "extraction_queue" {

  name = local.extraction_queue_name

  visibility_timeout_seconds = var.sqs_visibility_timeout_seconds
  message_retention_seconds  = 604800
  receive_wait_time_seconds  = 20

  redrive_policy = jsonencode({
    deadLetterTargetArn = aws_sqs_queue.extraction_dlq.arn
    maxReceiveCount     = var.sqs_max_receive_count
  })
  tags = merge(
    local.common_tags,
    {
      Name = local.extraction_queue_name
    }
  )
}
resource "aws_sqs_queue_policy" "s3_send_message" {

  queue_url = aws_sqs_queue.extraction_queue.id

  policy = templatefile(
    "${path.module}/templates/s3-sqs-policy.json.tpl",
    {
      queue_arn         = aws_sqs_queue.extraction_queue.arn
      bucket_arn        = aws_s3_bucket.raw.arn
      source_account_id = data.aws_caller_identity.current.account_id
    }
  )
}
