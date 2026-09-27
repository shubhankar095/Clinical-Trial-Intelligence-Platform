resource "aws_sns_topic" "alerts" {
  name = "${local.project_prefix}-alerts-${var.environment}"

  tags = merge(
    local.common_tags,
    {
      Name = "${local.project_prefix}-alerts-${var.environment}"
    }
  )
}

resource "aws_sns_topic_subscription" "email" {
  topic_arn = aws_sns_topic.alerts.arn
  protocol  = "email"
  endpoint  = var.alert_email
}
