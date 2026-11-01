resource "aws_ecr_lifecycle_policy" "this" {
  repository = aws_ecr_repository.this.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description = (
          "Remove untagged images older than ${var.untagged_image_retention_days} days"
        )

        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = var.untagged_image_retention_days
        }

        action = {
          type = "expire"
        }
      }
    ]
  })
}