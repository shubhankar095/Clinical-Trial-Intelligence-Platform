resource "aws_iam_role" "this" {
  name = var.role_name

  assume_role_policy = var.trust_policy_json

  tags = var.tags
}