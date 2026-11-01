variable "names" {
  description = "Complete names assigned to monitoring resources."

  type = object({
    processing_failures_filter  = string
    processing_successes_filter = string
    processing_duration_filter  = string
    dlq_alarm                   = string
    oldest_message_alarm        = string
    processing_failures_alarm   = string
    dashboard                   = string
  })

  validation {
    condition = alltrue([
      for name in values(var.names) :
      length(trimspace(name)) > 0
    ])

    error_message = "All monitoring names must be non-empty."
  }
}

variable "metric_namespace" {
  description = "CloudWatch namespace used for custom application metrics."
  type        = string

  validation {
    condition     = length(trimspace(var.metric_namespace)) > 0
    error_message = "metric_namespace must not be empty."
  }
}

variable "display" {
  description = "Human-readable values displayed in the CloudWatch dashboard."

  type = object({
    service_name      = string
    environment_name  = string
    dashboard_heading = string
  })

  validation {
    condition = alltrue([
      for value in values(var.display) :
      length(trimspace(value)) > 0
    ])

    error_message = "All monitoring display values must be non-empty."
  }
}

variable "alarm_descriptions" {
  description = "Descriptions assigned to operational alarms."

  type = object({
    dlq                 = string
    oldest_message      = string
    processing_failures = string
  })

  validation {
    condition = alltrue([
      for description in values(var.alarm_descriptions) :
      length(trimspace(description)) > 0
    ])

    error_message = "All monitoring alarm descriptions must be non-empty."
  }
}

variable "aws_region" {
  description = "AWS Region displayed in the CloudWatch dashboard."
  type        = string
}

variable "queue_name" {
  description = "Name of the primary SQS queue."
  type        = string
}

variable "dlq_name" {
  description = "Name of the SQS dead-letter queue."
  type        = string
}

variable "ecs_cluster_name" {
  description = "Name of the ECS cluster."
  type        = string
}

variable "ecs_service_name" {
  description = "Name of the ECS service."
  type        = string
}

variable "log_group_name" {
  description = "Name of the CloudWatch log group used by metric filters."
  type        = string
}

variable "alert_topic_arn" {
  description = "SNS topic ARN receiving operational alarm notifications."
  type        = string
}

variable "bootstrap_alarm_arn" {
  description = "ARN of the autoscaling bootstrap alarm."
  type        = string
}

variable "queue_drained_alarm_arn" {
  description = "ARN of the queue-drained autoscaling alarm."
  type        = string
}

variable "queue_empty_alarm_arn" {
  description = "ARN of the final scale-to-zero alarm."
  type        = string
}

variable "backlog_per_task_target" {
  description = "Target visible queue messages per running ECS task."
  type        = number

  validation {
    condition     = var.backlog_per_task_target > 0
    error_message = "backlog_per_task_target must be greater than zero."
  }
}

variable "oldest_message_alarm_seconds" {
  description = "Message age in seconds that triggers the oldest-message alarm."
  type        = number

  validation {
    condition     = var.oldest_message_alarm_seconds > 0
    error_message = "oldest_message_alarm_seconds must be greater than zero."
  }
}

variable "processing_failure_filter_pattern" {
  description = "CloudWatch Logs filter pattern used to identify processing failures."
  type        = string
}

variable "processing_success_filter_pattern" {
  description = "CloudWatch Logs filter pattern used to identify successful processing."
  type        = string
}

variable "processing_duration_filter_pattern" {
  description = "CloudWatch Logs filter pattern used to extract processing duration."
  type        = string
}

variable "tags" {
  description = "Optional tags applied to operational CloudWatch alarms."
  type        = map(string)
  default     = {}
}