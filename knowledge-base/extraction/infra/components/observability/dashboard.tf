resource "aws_cloudwatch_dashboard" "extraction" {
  dashboard_name = "${local.project_prefix}-extraction-${var.environment}"

  dashboard_body = jsonencode({
    start          = "-PT6H"
    periodOverride = "inherit"

    widgets = [
      {
        type   = "text"
        x      = 0
        y      = 0
        width  = 24
        height = 2

        properties = {
          markdown = join(
            "\n",
            [
              "# Clinical Knowledge Base: Extraction",
              "**Environment:** ${upper(var.environment)} | **Region:** ${var.aws_region}"
            ]
          )
        }
      },

      {
        type   = "metric"
        x      = 0
        y      = 2
        width  = 12
        height = 6

        properties = {
          title   = "Extraction Queue Workload"
          view    = "timeSeries"
          region  = var.aws_region
          period  = 60
          stat    = "Maximum"
          stacked = false

          metrics = [
            [
              "AWS/SQS",
              "ApproximateNumberOfMessagesVisible",
              "QueueName",
              var.extraction_queue_name,
              {
                label = "Messages Waiting"
                color = "#ff7f0e"
              }
            ],
            [
              "AWS/SQS",
              "ApproximateNumberOfMessagesNotVisible",
              "QueueName",
              var.extraction_queue_name,
              {
                label = "Messages In Flight"
                color = "#1f77b4"
              }
            ],
            [
              "AWS/SQS",
              "ApproximateNumberOfMessagesDelayed",
              "QueueName",
              var.extraction_queue_name,
              {
                label = "Messages Delayed"
                color = "#2ca02c"
              }
            ]
          ]
        }
      },
      {
        type   = "metric"
        x      = 12
        y      = 2
        width  = 12
        height = 6

        properties = {
          title   = "Queue Health"
          view    = "timeSeries"
          region  = var.aws_region
          period  = 60
          stat    = "Maximum"
          stacked = false

          metrics = [
            [
              "AWS/SQS",
              "ApproximateAgeOfOldestMessage",
              "QueueName",
              var.extraction_queue_name,
              {
                label = "Oldest Message Age"
                color = "#d62728"
              }
            ],
            [
              "AWS/SQS",
              "ApproximateNumberOfMessagesVisible",
              "QueueName",
              var.extraction_dlq_name,
              {
                label = "DLQ Messages"
                color = "#9467bd"
                yAxis = "right"
              }
            ]
          ]

          yAxis = {
            left = {
              min       = 0
              label     = "Age in seconds"
              showUnits = false
            }

            right = {
              min       = 0
              label     = "DLQ message count"
              showUnits = false
            }
          }

          annotations = {
            horizontal = [
              {
                label = "Maximum Acceptable Message Age"
                value = var.oldest_message_alarm_seconds
                color = "#d62728"
              }
            ]
          }
        }
      },
      {
        type   = "metric"
        x      = 0
        y      = 8
        width  = 8
        height = 6

        properties = {
          title                = "Documents Processed Successfully"
          view                 = "singleValue"
          region               = var.aws_region
          period               = 300
          stat                 = "Sum"
          sparkline            = true
          setPeriodToTimeRange = true

          metrics = [
            [
              local.extraction_metric_namespace,
              "ProcessingSuccesses",
              {
                label = "Successful Documents"
                color = "#2ca02c"
              }
            ]
          ]
        }
      },

      {
        type   = "metric"
        x      = 8
        y      = 8
        width  = 8
        height = 6

        properties = {
          title                = "Document Processing Failures"
          view                 = "singleValue"
          region               = var.aws_region
          period               = 300
          stat                 = "Sum"
          sparkline            = true
          setPeriodToTimeRange = true

          metrics = [
            [
              local.extraction_metric_namespace,
              "ProcessingFailures",
              {
                label = "Processing Failures"
                color = "#d62728"
              }
            ]
          ]
        }
      },

      {
        type   = "metric"
        x      = 16
        y      = 8
        width  = 8
        height = 6

        properties = {
          title   = "Processing Duration"
          view    = "timeSeries"
          region  = var.aws_region
          period  = 300
          stacked = false

          metrics = [
            [
              local.extraction_metric_namespace,
              "ProcessingDurationSeconds",
              {
                label = "Average Duration"
                stat  = "Average"
                color = "#1f77b4"
              }
            ],
            [
              local.extraction_metric_namespace,
              "ProcessingDurationSeconds",
              {
                label = "Maximum Duration"
                stat  = "Maximum"
                color = "#ff7f0e"
              }
            ]
          ]
        }
      },

      {
        type   = "metric"
        x      = 0
        y      = 14
        width  = 12
        height = 6

        properties = {
          title   = "Extraction Backlog per Running Task"
          view    = "timeSeries"
          region  = var.aws_region
          period  = 60
          stacked = false

          metrics = [
            [
              {
                expression = "IF(m1>0,IF(FILL(m2,0)>0,m1/FILL(m2,0),m1),IF(FILL(m2,0)>0,${var.backlog_per_task_target}/FILL(m2,0),${var.backlog_per_task_target}))"
                label      = "Backlog per Task"

                id = "e1"

                color = "#d62728"
              }
            ],
            [
              "AWS/SQS",
              "ApproximateNumberOfMessagesVisible",
              "QueueName",
              var.extraction_queue_name,
              {
                id      = "m1"
                visible = false
                stat    = "Maximum"
              }
            ],
            [
              "ECS/ContainerInsights",
              "RunningTaskCount",
              "ClusterName",
              var.ecs_cluster_name,
              "ServiceName",
              var.ecs_service_name,
              {
                id      = "m2"
                visible = false
                stat    = "Average"
              }
            ]
          ]

          annotations = {
            horizontal = [
              {
                label = "Target backlog per task"
                value = var.backlog_per_task_target
                color = "#2ca02c"
              }
            ]
          }

          yAxis = {
            left = {
              min = 0
            }
          }
        }
      },

      {
        type   = "metric"
        x      = 12
        y      = 14
        width  = 12
        height = 6

        properties = {
          title   = "ECS CPU Utilization"
          view    = "timeSeries"
          region  = var.aws_region
          period  = 300
          stat    = "Average"
          stacked = false
          yAxis = {
            left = {
              min = 0
              max = 100
            }
          }

          metrics = [
            [
              "AWS/ECS",
              "CPUUtilization",
              "ClusterName",
              var.ecs_cluster_name,
              "ServiceName",
              var.ecs_service_name,
              {
                label = "CPU Utilization"
                color = "#1f77b4"
              }
            ]
          ]
        }
      },

      {
        type   = "metric"
        x      = 0
        y      = 20
        width  = 12
        height = 6

        properties = {
          title   = "ECS Memory Utilization"
          view    = "timeSeries"
          region  = var.aws_region
          period  = 300
          stat    = "Average"
          stacked = false
          yAxis = {
            left = {
              min = 0
              max = 100
            }
          }

          metrics = [
            [
              "AWS/ECS",
              "MemoryUtilization",
              "ClusterName",
              var.ecs_cluster_name,
              "ServiceName",
              var.ecs_service_name,
              {
                label = "Memory Utilization"
                color = "#9467bd"
              }
            ]
          ]
        }
      },

      {
        type   = "alarm"
        x      = 0
        y      = 26
        width  = 24
        height = 6

        properties = {
          title = "Extraction Alarms and Scaling Status"

          alarms = [
            var.bootstrap_alarm_arn,
            aws_cloudwatch_metric_alarm.dlq_messages.arn,
            aws_cloudwatch_metric_alarm.oldest_message_age.arn,
            aws_cloudwatch_metric_alarm.processing_failures.arn,
            var.queue_drained_alarm_arn,
            var.queue_empty_alarm_arn
          ]
        }
      }
    ]
  })
}
