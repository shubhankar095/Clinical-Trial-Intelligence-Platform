resource "aws_opensearchserverless_collection" "this" {
  name = var.collection_name
  type = var.collection_type

  description = var.description

  collection_group_name = aws_opensearchserverless_collection_group.this.name

  depends_on = [
    aws_opensearchserverless_collection_group.this,
    aws_opensearchserverless_security_policy.encryption,
    aws_opensearchserverless_security_policy.network
  ]

  tags = merge(
    var.tags,
    {
      Name = var.collection_name
    }
  )
}