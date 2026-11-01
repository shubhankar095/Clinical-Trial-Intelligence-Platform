resource "aws_opensearchserverless_security_policy" "encryption" {
  name = var.encryption_policy_name
  type = "encryption"

  policy = jsonencode(
    merge(
      {
        Rules = [
          {
            ResourceType = "collection"

            Resource = [
              "collection/${var.collection_name}"
            ]
          }
        ]

        AWSOwnedKey = var.use_aws_owned_key
      },
      var.use_aws_owned_key
      ? {}
      : {
        KmsARN = var.kms_key_arn
      }
    )
  )
}
