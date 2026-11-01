resource "aws_appautoscaling_policy" "queue_drained_to_one" {
  name = var.names.queue_drained_policy

  policy_type = "StepScaling"

  resource_id        = aws_appautoscaling_target.ecs.resource_id
  scalable_dimension = aws_appautoscaling_target.ecs.scalable_dimension
  service_namespace  = aws_appautoscaling_target.ecs.service_namespace

  step_scaling_policy_configuration {
    adjustment_type         = "ExactCapacity"
    cooldown                = var.queue_drained_cooldown_seconds
    metric_aggregation_type = "Maximum"

    step_adjustment {
      metric_interval_upper_bound = 0
      scaling_adjustment          = 1
    }
  }
}

resource "aws_cloudwatch_metric_alarm" "queue_drained_to_one" {
  alarm_name        = var.names.queue_drained_alarm
  alarm_description = var.descriptions.queue_drained_alarm

  actions_enabled = true

  comparison_operator = "LessThanOrEqualToThreshold"
  threshold           = 0

  evaluation_periods  = var.queue_drained_evaluation_periods
  datapoints_to_alarm = var.queue_drained_evaluation_periods

  treat_missing_data = "notBreaching"

  metric_query {
    id = "e1"

    expression = "IF(FILL(m4,0)>1,m1+m2+m3,1)"
    label      = var.labels.queue_drained_expression

    return_data = true
  }

  metric_query {
    id          = "m1"
    return_data = false

    metric {
      namespace   = "AWS/SQS"
      metric_name = "ApproximateNumberOfMessagesVisible"

      period = 60
      stat   = "Maximum"

      dimensions = {
        QueueName = var.sqs_queue_name
      }
    }
  }

  metric_query {
    id          = "m2"
    return_data = false

    metric {
      namespace   = "AWS/SQS"
      metric_name = "ApproximateNumberOfMessagesNotVisible"

      period = 60
      stat   = "Maximum"

      dimensions = {
        QueueName = var.sqs_queue_name
      }
    }
  }

  metric_query {
    id          = "m3"
    return_data = false

    metric {
      namespace   = "AWS/SQS"
      metric_name = "ApproximateNumberOfMessagesDelayed"

      period = 60
      stat   = "Maximum"

      dimensions = {
        QueueName = var.sqs_queue_name
      }
    }
  }

  metric_query {
    id          = "m4"
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
    aws_appautoscaling_policy.queue_drained_to_one.arn
  ]

  tags = var.tags
}