# -----------------------------------------------------------------------------
# Shared Platform state
# -----------------------------------------------------------------------------

data "terraform_remote_state" "platform" {
  backend = "s3"

  config = {
    bucket       = var.platform_state_bucket
    key          = var.platform_state_key
    region       = var.platform_state_region
    use_lockfile = true
  }
}

data "aws_caller_identity" "current" {}

# -----------------------------------------------------------------------------
# S3 to SQS event delivery
# -----------------------------------------------------------------------------

resource "aws_sqs_queue_policy" "s3_send_message" {
  queue_url = module.extraction_queue.queue_url

  policy = templatefile(
    "${path.module}/templates/s3-sqs-policy.json.tpl",
    {
      queue_arn         = module.extraction_queue.queue_arn
      bucket_arn        = local.platform.raw_bucket_arn
      source_account_id = data.aws_caller_identity.current.account_id
    }
  )
}

resource "aws_s3_bucket_notification" "raw_uploads" {
  bucket = local.platform.raw_bucket_name

  queue {
    queue_arn = module.extraction_queue.queue_arn

    events = [
      "s3:ObjectCreated:*"
    ]

    filter_prefix = "documents/"
  }

  depends_on = [
    aws_sqs_queue_policy.s3_send_message
  ]
}
