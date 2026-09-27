variable "project_name" {
  description = "Project name"
  type        = string
  default     = "clinical-kb"
}

variable "aws_region" {
  description = "AWS Region"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Deployment environment"
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "uat", "stage", "prod"], var.environment)
    error_message = "environment must be dev, uat, stage, or prod."
  }
}

variable "raw_bucket_name" {
  description = "Raw Data S3 Bucket name"
  type        = string
  default     = "raw"
}

variable "canonical_bucket_name" {
  description = "Canonical Data S3 bucket name"
  type        = string
  default     = "canonical"
}

variable "ecs_min_capacity" {
  description = "Minimum ECS capacity"
  type        = number
  default     = 0

  validation {
    condition     = var.ecs_min_capacity >= 0
    error_message = "ecs_min_capacity must be zero or greater."
  }
}

variable "ecs_max_capacity" {
  description = "Maximum ECS capacity"
  type        = number
  default     = 10

  validation {
    condition     = var.ecs_max_capacity >= var.ecs_min_capacity
    error_message = "ecs_max_capacity must be greater than or equal to ecs_min_capacity."
  }
}

variable "ecs_cpu" {
  description = "ECS Fargate task CPU units"
  type        = number
  default     = 1024

  validation {
    condition = contains(
      [256, 512, 1024, 2048, 4096, 8192, 16384],
      var.ecs_cpu
    )

    error_message = "ecs_cpu must be a supported Fargate CPU value."
  }
}

variable "ecs_memory" {
  description = "ECS Fargate task memory in MiB"
  type        = number
  default     = 2048

  validation {
    condition     = var.ecs_memory > 0
    error_message = "ecs_memory must be greater than zero."
  }
}


variable "image_tag" {
  description = "ECR image tag deployed to the extraction ECS service"
  type        = string

  validation {
    condition = (
      length(trimspace(var.image_tag)) > 0
      && var.image_tag != "latest"
    )

    error_message = "image_tag must be non-empty and cannot be 'latest'."
  }

  validation {
    condition = (
      var.environment == "dev"
      || startswith(var.image_tag, "${var.environment}-")
      || (
        var.environment == "prod"
        && (
          startswith(var.image_tag, "v")
          || can(regex("^[0-9a-f]{7,40}$", var.image_tag))
        )
      )
    )

    error_message = "Use dev for development, environment-prefixed tags for UAT/stage, and a version or Git SHA for production."
  }
}

variable "alert_email" {
  description = "Email address subscribed to operational SNS alerts"
  type        = string
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days"
  type        = number
  default     = 30
}

variable "sqs_visibility_timeout_seconds" {
  description = "Initial visibility lease for a received extraction message"
  type        = number
  default     = 600

  validation {
    condition = (
      var.sqs_visibility_timeout_seconds > 0
      && var.sqs_visibility_timeout_seconds <= 43200
    )

    error_message = "sqs_visibility_timeout_seconds must be between 1 and 43200."
  }

  validation {
    condition = (
      var.sqs_visibility_timeout_seconds
      > var.sqs_visibility_heartbeat_seconds
    )

    error_message = "sqs_visibility_timeout_seconds must be greater than sqs_visibility_heartbeat_seconds."
  }
}

variable "sqs_max_receive_count" {
  description = "Number of failed receives before a message is moved to the DLQ"
  type        = number
  default     = 5

  validation {
    condition     = var.sqs_max_receive_count >= 1
    error_message = "sqs_max_receive_count must be at least 1."
  }
}

variable "oldest_message_alarm_seconds" {
  description = "Maximum acceptable age of the oldest visible extraction message"
  type        = number
  default     = 900

  validation {
    condition     = var.oldest_message_alarm_seconds > 0
    error_message = "oldest_message_alarm_seconds must be greater than zero."
  }
}

variable "vpc_cidr" {
  description = "CIDR block assigned to the extraction VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "public_subnet_a_cidr" {
  description = "CIDR block assigned to the first public subnet"
  type        = string
  default     = "10.0.1.0/24"
}

variable "public_subnet_b_cidr" {
  description = "CIDR block assigned to the second public subnet"
  type        = string
  default     = "10.0.2.0/24"
}


variable "processing_schema_version" {
  description = "Version of the extraction output schema"
  type        = string
  default     = "extraction-v1"

  validation {
    condition = (
      length(
        trimspace(
          var.processing_schema_version
        )
      ) > 0
    )

    error_message = "processing_schema_version must not be empty."
  }
}

variable "sqs_visibility_extension_seconds" {
  description = "Visibility lease applied while document processing is active"
  type        = number
  default     = 600

  validation {
    condition = (
      var.sqs_visibility_extension_seconds > 0
      && var.sqs_visibility_extension_seconds <= 43200
    )

    error_message = "sqs_visibility_extension_seconds must be between 1 and 43200."
  }
}

variable "sqs_visibility_heartbeat_seconds" {
  description = "Interval between SQS visibility lease renewals"
  type        = number
  default     = 180

  validation {
    condition = (
      var.sqs_visibility_heartbeat_seconds > 0
      && (
        var.sqs_visibility_heartbeat_seconds
        < var.sqs_visibility_extension_seconds
      )
    )

    error_message = "sqs_visibility_heartbeat_seconds must be positive and less than sqs_visibility_extension_seconds."
  }
}

variable "processing_claim_lease_seconds" {
  description = "Duration of an exclusive document-processing claim"
  type        = number
  default     = 1800

  validation {
    condition = (
      var.processing_claim_lease_seconds
      > var.sqs_visibility_extension_seconds
    )

    error_message = "processing_claim_lease_seconds must be greater than sqs_visibility_extension_seconds."
  }

  validation {
    condition = (
      var.processing_claim_lease_seconds
      <= 86400
    )

    error_message = "processing_claim_lease_seconds must not exceed 86400 seconds."
  }
}


variable "backlog_per_task_target" {
  description = "Target number of visible SQS messages per running extraction task"
  type        = number
  default     = 5

  validation {
    condition = (
      var.backlog_per_task_target > 0
    )

    error_message = "backlog_per_task_target must be greater than zero."
  }
}

variable "ecs_scale_out_cooldown_seconds" {
  description = "Seconds before another backlog-based scale-out evaluation"
  type        = number
  default     = 60

  validation {
    condition = (
      var.ecs_scale_out_cooldown_seconds >= 0
      && var.ecs_scale_out_cooldown_seconds <= 3600
    )

    error_message = "ecs_scale_out_cooldown_seconds must be between 0 and 3600."
  }
}

variable "ecs_scale_in_cooldown_seconds" {
  description = "Seconds between proportional backlog-based target-tracking scale-in actions"
  type        = number
  default     = 300

  validation {
    condition = (
      var.ecs_scale_in_cooldown_seconds >= 0
      && var.ecs_scale_in_cooldown_seconds <= 3600
    )

    error_message = "ecs_scale_in_cooldown_seconds must be between 0 and 3600."
  }
}


variable "queue_drained_evaluation_periods" {
  description = "Consecutive one-minute empty queue periods required before reducing excess extraction workers directly to one"
  type        = number
  default     = 2

  validation {
    condition = (
      var.queue_drained_evaluation_periods >= 1
      && var.queue_drained_evaluation_periods < var.scale_to_zero_evaluation_periods
    )

    error_message = "queue_drained_evaluation_periods must be at least 1 and less than scale_to_zero_evaluation_periods."
  }
}

variable "queue_drained_scale_in_cooldown_seconds" {
  description = "Cooldown after reducing excess extraction workers directly to one"
  type        = number
  default     = 60

  validation {
    condition = (
      var.queue_drained_scale_in_cooldown_seconds >= 0
      && var.queue_drained_scale_in_cooldown_seconds <= 3600
    )

    error_message = "queue_drained_scale_in_cooldown_seconds must be between 0 and 3600."
  }
}

variable "scale_to_zero_evaluation_periods" {
  description = "Consecutive one-minute empty queue periods required before reducing the final extraction worker to zero"
  type        = number
  default     = 5

  validation {
    condition = (
      var.scale_to_zero_evaluation_periods >= 5
      && var.scale_to_zero_evaluation_periods <= 60
    )

    error_message = "scale_to_zero_evaluation_periods must be between 5 and 60."
  }
}

variable "idle_scale_to_zero_cooldown_seconds" {
  description = "Cooldown after reducing the final extraction worker to zero"
  type        = number
  default     = 300

  validation {
    condition = (
      var.idle_scale_to_zero_cooldown_seconds >= 0
      && var.idle_scale_to_zero_cooldown_seconds <= 3600
    )

    error_message = "idle_scale_to_zero_cooldown_seconds must be between 0 and 3600."
  }
}

variable "processing_claim_heartbeat_seconds" {
  description = "Interval between DynamoDB processing-claim lease renewals"
  type        = number
  default     = 300

  validation {
    condition = (
      var.processing_claim_heartbeat_seconds > 0
      && (
        var.processing_claim_heartbeat_seconds
        < var.processing_claim_lease_seconds
      )
    )

    error_message = "processing_claim_heartbeat_seconds must be positive and less than processing_claim_lease_seconds."
  }
}
