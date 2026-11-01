variable "names" {
  description = "Complete names assigned to autoscaling policies and alarms."

  type = object({
    backlog_policy       = string
    bootstrap_policy     = string
    bootstrap_alarm      = string
    queue_drained_policy = string
    queue_drained_alarm  = string
    idle_policy          = string
    queue_empty_alarm    = string
  })

  validation {
    condition = alltrue([
      for name in values(var.names) :
      length(trimspace(name)) > 0
    ])

    error_message = "All autoscaling names must be non-empty."
  }
}

variable "labels" {
  description = "CloudWatch labels used by autoscaling metric queries."

  type = object({
    visible_messages         = string
    running_tasks            = string
    backlog_per_task         = string
    bootstrap_expression     = string
    queue_drained_expression = string
    idle_expression          = string
  })

  validation {
    condition = alltrue([
      for label in values(var.labels) :
      length(trimspace(label)) > 0
    ])

    error_message = "All autoscaling labels must be non-empty."
  }
}

variable "descriptions" {
  description = "Descriptions assigned to autoscaling alarms."

  type = object({
    bootstrap_alarm     = string
    queue_drained_alarm = string
    idle_alarm          = string
  })

  validation {
    condition = alltrue([
      for description in values(var.descriptions) :
      length(trimspace(description)) > 0
    ])

    error_message = "All autoscaling alarm descriptions must be non-empty."
  }
}

variable "sqs_queue_name" {
  description = "Name of the SQS queue monitored for autoscaling."
  type        = string

  validation {
    condition     = length(trimspace(var.sqs_queue_name)) > 0
    error_message = "sqs_queue_name must not be empty."
  }
}

variable "ecs_cluster_name" {
  description = "Name of the ECS cluster containing the service."
  type        = string

  validation {
    condition     = length(trimspace(var.ecs_cluster_name)) > 0
    error_message = "ecs_cluster_name must not be empty."
  }
}

variable "ecs_service_name" {
  description = "Name of the ECS service controlled by autoscaling."
  type        = string

  validation {
    condition     = length(trimspace(var.ecs_service_name)) > 0
    error_message = "ecs_service_name must not be empty."
  }
}

variable "min_capacity" {
  description = "Minimum desired capacity registered for the ECS service."
  type        = number

  validation {
    condition     = var.min_capacity >= 0
    error_message = "min_capacity must be zero or greater."
  }
}

variable "max_capacity" {
  description = "Maximum desired capacity registered for the ECS service."
  type        = number

  validation {
    condition     = var.max_capacity >= var.min_capacity
    error_message = "max_capacity must be greater than or equal to min_capacity."
  }
}

variable "backlog_per_task_target" {
  description = "Target number of visible SQS messages per running ECS task."
  type        = number

  validation {
    condition     = var.backlog_per_task_target > 0
    error_message = "backlog_per_task_target must be greater than zero."
  }
}

variable "scale_out_cooldown_seconds" {
  description = "Cooldown between backlog-based scale-out actions."
  type        = number

  validation {
    condition = (
      var.scale_out_cooldown_seconds >= 0
      && var.scale_out_cooldown_seconds <= 3600
    )

    error_message = "scale_out_cooldown_seconds must be between 0 and 3600."
  }
}

variable "scale_in_cooldown_seconds" {
  description = "Cooldown between target-tracking scale-in actions."
  type        = number

  validation {
    condition = (
      var.scale_in_cooldown_seconds >= 0
      && var.scale_in_cooldown_seconds <= 3600
    )

    error_message = "scale_in_cooldown_seconds must be between 0 and 3600."
  }
}

variable "queue_drained_evaluation_periods" {
  description = "Consecutive empty periods required before reducing excess workers to one."
  type        = number

  validation {
    condition = (
      var.queue_drained_evaluation_periods >= 1
      && var.queue_drained_evaluation_periods < var.scale_to_zero_evaluation_periods
    )

    error_message = "queue_drained_evaluation_periods must be at least 1 and less than scale_to_zero_evaluation_periods."
  }
}

variable "queue_drained_cooldown_seconds" {
  description = "Cooldown after reducing excess workers directly to one."
  type        = number

  validation {
    condition = (
      var.queue_drained_cooldown_seconds >= 0
      && var.queue_drained_cooldown_seconds <= 3600
    )

    error_message = "queue_drained_cooldown_seconds must be between 0 and 3600."
  }
}

variable "scale_to_zero_evaluation_periods" {
  description = "Consecutive empty periods required before scaling the final worker to zero."
  type        = number

  validation {
    condition = (
      var.scale_to_zero_evaluation_periods >= 1
      && var.scale_to_zero_evaluation_periods <= 60
    )

    error_message = "scale_to_zero_evaluation_periods must be between 1 and 60."
  }
}

variable "idle_scale_to_zero_cooldown_seconds" {
  description = "Cooldown after scaling the final worker to zero."
  type        = number

  validation {
    condition = (
      var.idle_scale_to_zero_cooldown_seconds >= 0
      && var.idle_scale_to_zero_cooldown_seconds <= 3600
    )

    error_message = "idle_scale_to_zero_cooldown_seconds must be between 0 and 3600."
  }
}

variable "tags" {
  description = "Optional tags applied to the CloudWatch scaling alarms."
  type        = map(string)
  default     = {}
}