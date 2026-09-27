resource "aws_cloudwatch_log_metric_filter" "processing_failures" {

  name = "${local.project_prefix}-extraction-processing-failures-${var.environment}"

  log_group_name = var.cloudwatch_log_group_name

  pattern = "\"Message processing failed\""

  metric_transformation {

    name = "ProcessingFailures"

    namespace = local.extraction_metric_namespace

    value = "1"

    unit = "Count"
  }


}

resource "aws_cloudwatch_log_metric_filter" "processing_successes" {
  name = "${local.project_prefix}-extraction-processing-successes-${var.environment}"

  log_group_name = var.cloudwatch_log_group_name

  pattern = "{ $.event = \"document_processed\" && $.processing_status = \"SUCCESS\" }"

  metric_transformation {
    name      = "ProcessingSuccesses"
    namespace = local.extraction_metric_namespace
    value     = "1"
    unit      = "Count"
  }
}

resource "aws_cloudwatch_log_metric_filter" "processing_duration" {
  name = "${local.project_prefix}-extraction-processing-duration-${var.environment}"

  log_group_name = var.cloudwatch_log_group_name

  pattern = "{ $.event = \"document_processed\" && $.duration_seconds = * }"

  metric_transformation {
    name      = "ProcessingDurationSeconds"
    namespace = local.extraction_metric_namespace
    value     = "$.duration_seconds"
    unit      = "Seconds"
  }
}
