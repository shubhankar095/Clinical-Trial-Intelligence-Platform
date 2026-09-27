resource "aws_ecr_repository" "extraction" {
  name = "${local.project_prefix}-extraction-${var.environment}"

  force_delete = var.environment == "dev"

  image_tag_mutability = (
    var.environment == "dev"
    ? "MUTABLE"
    : "IMMUTABLE"
  )

  image_scanning_configuration {
    scan_on_push = true
  }

  tags = merge(
    local.common_tags,
    {
      Name = "${local.project_prefix}-extraction-${var.environment}"
    }
  )
}


resource "aws_ecr_lifecycle_policy" "extraction" {
  repository = aws_ecr_repository.extraction.name

  policy = jsonencode({
    rules = [
      {
        rulePriority = 1
        description  = "Remove untagged images older than 14 days"

        selection = {
          tagStatus   = "untagged"
          countType   = "sinceImagePushed"
          countUnit   = "days"
          countNumber = 14
        }

        action = {
          type = "expire"
        }
      }
    ]
  })
}
