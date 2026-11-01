variable "queue_name" {
  description = "Name assigned to the primary SQS queue."
  type        = string

  validation {
    condition     = length(trimspace(var.queue_name)) > 0
    error_message = "queue_name must not be empty."
  }
}

variable "dlq_name" {
  description = "Name assigned to the dead-letter queue."
  type        = string

  validation {
    condition     = length(trimspace(var.dlq_name)) > 0
    error_message = "dlq_name must not be empty."
  }
}

variable "visibility_timeout_seconds" {
  description = "Time in seconds that a received message remains invisible to other consumers."
  type        = number

  validation {
    condition = (
      var.visibility_timeout_seconds >= 0
      && var.visibility_timeout_seconds <= 43200
    )

    error_message = "visibility_timeout_seconds must be between 0 and 43200 seconds."
  }
}

variable "message_retention_seconds" {
  description = "Time in seconds that the primary queue retains messages."
  type        = number
  default     = 604800

  validation {
    condition = (
      var.message_retention_seconds >= 60
      && var.message_retention_seconds <= 1209600
    )

    error_message = "message_retention_seconds must be between 60 and 1209600 seconds."
  }
}

variable "receive_wait_time_seconds" {
  description = "Long-polling wait time in seconds for ReceiveMessage calls."
  type        = number
  default     = 20

  validation {
    condition = (
      var.receive_wait_time_seconds >= 0
      && var.receive_wait_time_seconds <= 20
    )

    error_message = "receive_wait_time_seconds must be between 0 and 20 seconds."
  }
}

variable "dlq_message_retention_seconds" {
  description = "Time in seconds that the dead-letter queue retains messages."
  type        = number
  default     = 1209600

  validation {
    condition = (
      var.dlq_message_retention_seconds >= 60
      && var.dlq_message_retention_seconds <= 1209600
    )

    error_message = "dlq_message_retention_seconds must be between 60 and 1209600 seconds."
  }
}

variable "max_receive_count" {
  description = "Number of failed message receives before SQS moves the message to the dead-letter queue."
  type        = number

  validation {
    condition     = var.max_receive_count >= 1
    error_message = "max_receive_count must be at least 1."
  }
}

variable "tags" {
  description = "Tags applied to the primary queue and dead-letter queue."
  type        = map(string)
  default     = {}
}