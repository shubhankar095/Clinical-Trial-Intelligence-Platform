resource "aws_cloudwatch_metric_alarm" "dlq_messages" {

  alarm_name = "${local.project_prefix}-extraction-dlq-messages-${var.environment}"

  alarm_description = "Extraction messages have reached the dead-letter queue."

  namespace   = "AWS/SQS"
  metric_name = "ApproximateNumberOfMessagesVisible"

  statistic = "Maximum"

  period              = 60
  evaluation_periods  = 1
  datapoints_to_alarm = 1

  threshold = 0

  comparison_operator = "GreaterThanThreshold"

  treat_missing_data = "notBreaching"

  dimensions = {
    QueueName = var.extraction_dlq_name
  }

  alarm_actions = [
    var.alert_topic_arn
  ]

  tags = local.common_tags
}

resource "aws_cloudwatch_metric_alarm" "oldest_message_age" {

  alarm_name = "${local.project_prefix}-extraction-oldest-message-${var.environment}"

  alarm_description = "Extraction messages have remained unprocessed for more than 15 minutes."

  namespace   = "AWS/SQS"
  metric_name = "ApproximateAgeOfOldestMessage"

  statistic = "Maximum"

  period              = 60
  evaluation_periods  = 5
  datapoints_to_alarm = 5

  threshold = var.oldest_message_alarm_seconds

  comparison_operator = "GreaterThanThreshold"

  treat_missing_data = "notBreaching"

  dimensions = {
    QueueName = var.extraction_queue_name
  }

  alarm_actions = [
    var.alert_topic_arn
  ]

  tags = local.common_tags
}

resource "aws_cloudwatch_metric_alarm" "processing_failures" {

  alarm_name = "${local.project_prefix}-extraction-processing-failures-${var.environment}"

  alarm_description = "The extraction worker logged one or more message-processing failures."

  namespace   = local.extraction_metric_namespace
  metric_name = "ProcessingFailures"

  statistic = "Sum"

  period              = 300
  evaluation_periods  = 1
  datapoints_to_alarm = 1

  threshold = 0

  comparison_operator = "GreaterThanThreshold"

  treat_missing_data = "notBreaching"

  alarm_actions = [
    var.alert_topic_arn
  ]

  tags = local.common_tags
}
