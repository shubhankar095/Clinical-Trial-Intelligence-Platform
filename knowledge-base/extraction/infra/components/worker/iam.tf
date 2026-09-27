resource "aws_iam_role" "ecs_task_role" {

  name = "${local.project_prefix}-task-role-${var.environment}"

  assume_role_policy = templatefile(
    "${path.module}/templates/extraction-trust-policy.json.tpl",
    {}
  )
}

resource "aws_iam_role" "ecs_execution_role" {

  name = "${local.project_prefix}-execution-role-${var.environment}"

  assume_role_policy = templatefile(
    "${path.module}/templates/extraction-trust-policy.json.tpl",
    {}
  )
}

resource "aws_iam_policy" "extraction" {

  name = "${local.project_prefix}-permissions-${var.environment}"

  policy = templatefile(
    "${path.module}/templates/extraction-permissions-policy.json.tpl",
    {
      raw_bucket              = var.raw_bucket_name
      canonical_bucket        = var.canonical_bucket_name
      queue_arn               = var.extraction_queue_arn
      processing_registry_arn = var.processing_registry_arn
    }
  )
}

resource "aws_iam_role_policy_attachment" "task" {

  role = aws_iam_role.ecs_task_role.name

  policy_arn = aws_iam_policy.extraction.arn
}


resource "aws_iam_role_policy_attachment" "execution" {

  role = aws_iam_role.ecs_execution_role.name

  policy_arn = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
}
