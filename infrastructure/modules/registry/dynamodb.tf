resource "aws_dynamodb_table" "this" {
  name = var.table_name

  billing_mode = "PAY_PER_REQUEST"
  hash_key     = var.partition_key

  attribute {
    name = var.partition_key
    type = "S"
  }

  point_in_time_recovery {
    enabled = true
  }

  server_side_encryption {
    enabled = true
  }

  ttl {
    attribute_name = var.ttl_attribute_name
    enabled        = true
  }

  tags = merge(
    var.tags,
    {
      Name = var.table_name
    }
  )
}