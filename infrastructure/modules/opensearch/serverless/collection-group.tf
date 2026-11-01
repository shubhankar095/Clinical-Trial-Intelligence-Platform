resource "aws_opensearchserverless_collection_group" "this" {
  name        = var.collection_group_name
  description = "NextGen collection group for ${var.collection_name}"

  generation       = var.collection_group_generation
  standby_replicas = var.collection_group_standby_replicas

  capacity_limits = [
    {
      min_indexing_capacity_in_ocu = var.min_indexing_capacity_in_ocu
      max_indexing_capacity_in_ocu = var.max_indexing_capacity_in_ocu
      min_search_capacity_in_ocu   = var.min_search_capacity_in_ocu
      max_search_capacity_in_ocu   = var.max_search_capacity_in_ocu
    }
  ]

  tags = merge(
    var.tags,
    {
      Name = var.collection_group_name
    }
  )

  lifecycle {
    precondition {
      condition = (
        var.collection_group_generation != "NEXTGEN"
        || var.collection_group_standby_replicas == "ENABLED"
      )

      error_message = "NEXTGEN OpenSearch Serverless collection groups require standby replicas to be ENABLED."
    }

    precondition {
      condition = (
        var.min_indexing_capacity_in_ocu
        <= var.max_indexing_capacity_in_ocu
      )

      error_message = "min_indexing_capacity_in_ocu must be less than or equal to max_indexing_capacity_in_ocu."
    }

    precondition {
      condition = (
        var.min_search_capacity_in_ocu
        <= var.max_search_capacity_in_ocu
      )

      error_message = "min_search_capacity_in_ocu must be less than or equal to max_search_capacity_in_ocu."
    }
  }
}