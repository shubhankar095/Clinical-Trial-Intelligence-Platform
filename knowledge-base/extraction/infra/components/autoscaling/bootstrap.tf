resource "aws_appautoscaling_policy" "bootstrap_scale_out" {
  name = "${local.project_prefix}-bootstrap-scale-out-${var.environment}"

  policy_type = "StepScaling"

  resource_id        = aws_appautoscaling_target.ecs.resource_id
  scalable_dimension = aws_appautoscaling_target.ecs.scalable_dimension
  service_namespace  = aws_appautoscaling_target.ecs.service_namespace

  step_scaling_policy_configuration {
    adjustment_type         = "ExactCapacity"
    cooldown                = var.ecs_scale_out_cooldown_seconds
    metric_aggregation_type = "Maximum"

    step_adjustment {
      metric_interval_lower_bound = 0
      scaling_adjustment          = 1
    }
  }
}

resource "aws_cloudwatch_metric_alarm" "bootstrap_queue_not_empty" {
  alarm_name = "${local.project_prefix}-bootstrap-queue-not-empty-${var.environment}"

  alarm_description = "Start exactly one extraction worker when visible messages exist and no ECS worker is running."

  comparison_operator = "GreaterThanThreshold"

  threshold = 0

  evaluation_periods  = 1
  datapoints_to_alarm = 1

  treat_missing_data = "notBreaching"

  metric_query {
    id = "e1"

    expression = "IF(FILL(m2,0)<1,m1,0)"

    label = "Visible messages requiring bootstrap"

    return_data = true
  }

  metric_query {
    id = "m1"

    return_data = false

    metric {
      namespace   = "AWS/SQS"
      metric_name = "ApproximateNumberOfMessagesVisible"

      period = 60
      stat   = "Maximum"

      dimensions = {
        QueueName = var.extraction_queue_name
      }
    }
  }

  metric_query {
    id = "m2"

    return_data = false

    metric {
      namespace   = "ECS/ContainerInsights"
      metric_name = "RunningTaskCount"

      period = 60
      stat   = "Average"

      dimensions = {
        ClusterName = var.ecs_cluster_name
        ServiceName = var.ecs_service_name
      }
    }
  }

  alarm_actions = [
    aws_appautoscaling_policy.bootstrap_scale_out.arn
  ]

  tags = local.common_tags
}
