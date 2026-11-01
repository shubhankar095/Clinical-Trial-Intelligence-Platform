resource "aws_ecr_repository" "this" {
  name = var.repository_name

  force_delete = var.force_delete

  image_tag_mutability = var.image_tag_mutability

  image_scanning_configuration {
    scan_on_push = var.scan_on_push
  }

  tags = merge(
    var.tags,
    {
      Name = var.repository_name
    }
  )
}