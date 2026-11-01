resource "aws_cloudwatch_log_metric_filter" "processing_failures" {
  name = var.names.processing_failures_filter

  log_group_name = var.log_group_name
  pattern        = var.processing_failure_filter_pattern

  metric_transformation {
    name      = "ProcessingFailures"
    namespace = var.metric_namespace
    value     = "1"
    unit      = "Count"
  }
}

resource "aws_cloudwatch_log_metric_filter" "processing_successes" {
  name = var.names.processing_successes_filter

  log_group_name = var.log_group_name
  pattern        = var.processing_success_filter_pattern

  metric_transformation {
    name      = "ProcessingSuccesses"
    namespace = var.metric_namespace
    value     = "1"
    unit      = "Count"
  }
}

resource "aws_cloudwatch_log_metric_filter" "processing_duration" {
  name = var.names.processing_duration_filter

  log_group_name = var.log_group_name
  pattern        = var.processing_duration_filter_pattern

  metric_transformation {
    name      = "ProcessingDurationSeconds"
    namespace = var.metric_namespace
    value     = "$.duration_seconds"
    unit      = "Seconds"
  }
}