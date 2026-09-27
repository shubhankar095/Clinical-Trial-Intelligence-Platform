resource "aws_s3_bucket" "raw" {
  bucket = var.raw_bucket_name

  force_destroy = var.environment == "dev"

  tags = merge(
    local.common_tags,
    {
      Name = var.raw_bucket_name
    }
  )
}

resource "aws_s3_bucket" "canonical" {
  bucket = var.canonical_bucket_name

  force_destroy = var.environment == "dev"

  tags = merge(
    local.common_tags,
    {
      Name = var.canonical_bucket_name
    }
  )
}

resource "aws_s3_bucket_versioning" "raw" {

  bucket = aws_s3_bucket.raw.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_versioning" "canonical" {

  bucket = aws_s3_bucket.canonical.id

  versioning_configuration {
    status = "Enabled"
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "raw" {

  bucket = aws_s3_bucket.raw.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_server_side_encryption_configuration" "canonical" {

  bucket = aws_s3_bucket.canonical.id

  rule {
    apply_server_side_encryption_by_default {
      sse_algorithm = "AES256"
    }
  }
}

resource "aws_s3_bucket_public_access_block" "raw" {

  bucket = aws_s3_bucket.raw.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_public_access_block" "canonical" {

  bucket = aws_s3_bucket.canonical.id

  block_public_acls       = true
  block_public_policy     = true
  ignore_public_acls      = true
  restrict_public_buckets = true
}

resource "aws_s3_bucket_notification" "raw_uploads" {

  bucket = aws_s3_bucket.raw.id

  queue {

    queue_arn = aws_sqs_queue.extraction_queue.arn

    events = [
      "s3:ObjectCreated:*"
    ]

    filter_prefix = "documents/"
  }

  depends_on = [
    aws_sqs_queue_policy.s3_send_message
  ]
}

resource "aws_s3_bucket_lifecycle_configuration" "raw" {
  bucket = aws_s3_bucket.raw.id

  depends_on = [
    aws_s3_bucket_versioning.raw
  ]

  rule {
    id     = "cleanup-noncurrent-raw-versions"
    status = "Enabled"

    filter {}

    noncurrent_version_expiration {
      noncurrent_days = 30
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}

resource "aws_s3_bucket_lifecycle_configuration" "canonical" {
  bucket = aws_s3_bucket.canonical.id

  depends_on = [
    aws_s3_bucket_versioning.canonical
  ]

  rule {
    id     = "cleanup-noncurrent-canonical-versions"
    status = "Enabled"

    filter {}

    noncurrent_version_expiration {
      noncurrent_days = 30
    }

    abort_incomplete_multipart_upload {
      days_after_initiation = 7
    }
  }
}
