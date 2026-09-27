resource "aws_appautoscaling_policy" "backlog_per_task" {
  name = "${local.project_prefix}-backlog-per-task-${var.environment}"

  policy_type = "TargetTrackingScaling"

  resource_id        = aws_appautoscaling_target.ecs.resource_id
  scalable_dimension = aws_appautoscaling_target.ecs.scalable_dimension
  service_namespace  = aws_appautoscaling_target.ecs.service_namespace

  target_tracking_scaling_policy_configuration {
    target_value = var.backlog_per_task_target

    scale_out_cooldown = var.ecs_scale_out_cooldown_seconds
    scale_in_cooldown  = var.ecs_scale_in_cooldown_seconds

    disable_scale_in = false

    customized_metric_specification {
      metrics {
        id          = "m1"
        label       = "Visible extraction messages"
        return_data = false

        metric_stat {
          metric {
            namespace   = "AWS/SQS"
            metric_name = "ApproximateNumberOfMessagesVisible"

            dimensions {
              name  = "QueueName"
              value = var.extraction_queue_name
            }
          }


          stat = "Maximum"
        }
      }

      metrics {
        id          = "m2"
        label       = "Running extraction tasks"
        return_data = false

        metric_stat {
          metric {
            namespace   = "ECS/ContainerInsights"
            metric_name = "RunningTaskCount"

            dimensions {
              name  = "ClusterName"
              value = var.ecs_cluster_name
            }

            dimensions {
              name  = "ServiceName"
              value = var.ecs_service_name
            }
          }


          stat = "Average"
        }
      }

      metrics {
        id          = "e1"
        label       = "Extraction backlog per task"
        expression  = "IF(m1>0,IF(FILL(m2,0)>0,m1/FILL(m2,0),m1),IF(FILL(m2,0)>0,${var.backlog_per_task_target}/FILL(m2,0),${var.backlog_per_task_target}))"
        return_data = true
      }
    }
  }
}
