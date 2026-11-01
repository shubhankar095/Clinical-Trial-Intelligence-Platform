resource "aws_opensearchserverless_access_policy" "ingestion" {
  name = local.names.opensearch_access_policy
  type = "data"

  description = (
    "Allow the Ingestion task role to manage its knowledge-base indexes."
  )

  policy = jsonencode(
    [
      {
        Description = (
          "Ingestion access to the shared knowledge-base collection."
        )

        Rules = [
          {
            ResourceType = "collection"

            Resource = [
              local.opensearch_access.collection_resource
            ]

            Permission = (
              local.opensearch_access.collection_permissions
            )
          },
          {
            ResourceType = "index"

            Resource = [
              local.opensearch_access.index_resource
            ]

            Permission = (
              local.opensearch_access.index_permissions
            )
          }
        ]

        Principal = [
          module.ingestion_task_role.role_arn
        ]
      }
    ]
  )
}