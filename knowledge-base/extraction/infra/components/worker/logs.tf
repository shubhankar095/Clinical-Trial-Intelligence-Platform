resource "aws_cloudwatch_log_group" "extraction" {

  name = "/ecs/${local.project_prefix}-extraction-${var.environment}"

  retention_in_days = var.log_retention_days

  tags = merge(
    local.common_tags,
    {
      Name = "${local.project_prefix}-extraction-${var.environment}"
    }
  )
}
