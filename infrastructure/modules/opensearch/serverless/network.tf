resource "aws_opensearchserverless_security_policy" "network" {
  name = var.network_policy_name
  type = "network"

  policy = jsonencode(
    [
      merge(
        {
          Description = (
            "Network access policy for ${var.collection_name}"
          )

          Rules = [
            {
              ResourceType = "collection"

              Resource = [
                "collection/${var.collection_name}"
              ]
            },
            {
              ResourceType = "dashboard"

              Resource = [
                "collection/${var.collection_name}"
              ]
            }
          ]

          AllowFromPublic = var.allow_public_access
        },
        var.allow_public_access
        ? {}
        : {
          SourceVPCEs = var.source_vpce_ids
        }
      )
    ]
  )
}