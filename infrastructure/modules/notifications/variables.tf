variable "topic_name" {
  description = "Name assigned to the SNS alert topic."
  type        = string

  validation {
    condition = (
      length(trimspace(var.topic_name)) > 0
    )

    error_message = "topic_name must not be empty."
  }
}

variable "email_endpoint" {
  description = "Email address subscribed to the SNS alert topic."
  type        = string

  validation {
    condition = (
      length(trimspace(var.email_endpoint)) > 0
    )

    error_message = "email_endpoint must not be empty."
  }
}

variable "tags" {
  description = "Tags applied to the SNS alert topic."
  type        = map(string)
  default     = {}
}