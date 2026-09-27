resource "aws_dynamodb_table" "processing_registry" {

  name = local.processing_registry_table_name

  billing_mode = "PAY_PER_REQUEST"
  hash_key     = "document_id"

  attribute {
    name = "document_id"
    type = "S"
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled = true
  }

  ttl {
    attribute_name = "ttl"
    enabled        = true
  }

  tags = merge(
    local.common_tags,
    {
      Name = "${local.project_prefix}-extraction-processing-${var.environment}"
    }
  )
}
