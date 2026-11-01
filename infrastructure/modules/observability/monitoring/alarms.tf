resource "aws_cloudwatch_metric_alarm" "dlq_messages" {
  alarm_name        = var.names.dlq_alarm
  alarm_description = var.alarm_descriptions.dlq

  namespace   = "AWS/SQS"
  metric_name = "ApproximateNumberOfMessagesVisible"

  statistic = "Maximum"

  period              = 60
  evaluation_periods  = 1
  datapoints_to_alarm = 1

  threshold           = 0
  comparison_operator = "GreaterThanThreshold"

  treat_missing_data = "notBreaching"

  dimensions = {
    QueueName = var.dlq_name
  }

  alarm_actions = [
    var.alert_topic_arn
  ]

  tags = var.tags
}

resource "aws_cloudwatch_metric_alarm" "oldest_message_age" {
  alarm_name        = var.names.oldest_message_alarm
  alarm_description = var.alarm_descriptions.oldest_message

  namespace   = "AWS/SQS"
  metric_name = "ApproximateAgeOfOldestMessage"

  statistic = "Maximum"

  period              = 60
  evaluation_periods  = 5
  datapoints_to_alarm = 5

  threshold           = var.oldest_message_alarm_seconds
  comparison_operator = "GreaterThanThreshold"

  treat_missing_data = "notBreaching"

  dimensions = {
    QueueName = var.queue_name
  }

  alarm_actions = [
    var.alert_topic_arn
  ]

  tags = var.tags
}

resource "aws_cloudwatch_metric_alarm" "processing_failures" {
  alarm_name        = var.names.processing_failures_alarm
  alarm_description = var.alarm_descriptions.processing_failures

  namespace   = var.metric_namespace
  metric_name = "ProcessingFailures"

  statistic = "Sum"

  period              = 300
  evaluation_periods  = 1
  datapoints_to_alarm = 1

  threshold           = 0
  comparison_operator = "GreaterThanThreshold"

  treat_missing_data = "notBreaching"

  alarm_actions = [
    var.alert_topic_arn
  ]

  tags = var.tags
}