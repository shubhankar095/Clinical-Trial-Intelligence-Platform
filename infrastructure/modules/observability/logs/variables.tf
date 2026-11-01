variable "log_group_name" {
  description = "Name assigned to the CloudWatch log group."
  type        = string

  validation {
    condition = (
      length(trimspace(var.log_group_name)) > 0
    )

    error_message = "log_group_name must not be empty."
  }
}

variable "retention_in_days" {
  description = "Number of days CloudWatch retains log events."
  type        = number

  validation {
    condition = contains(
      [
        0,
        1,
        3,
        5,
        7,
        14,
        30,
        60,
        90,
        120,
        150,
        180,
        365,
        400,
        545,
        731,
        1096,
        1827,
        2192,
        2557,
        2922,
        3288,
        3653
      ],
      var.retention_in_days
    )

    error_message = "retention_in_days must be a supported CloudWatch Logs retention value."
  }
}

variable "name_tag" {
  description = "Value assigned to the Name tag of the CloudWatch log group."
  type        = string

  validation {
    condition = (
      length(trimspace(var.name_tag)) > 0
    )

    error_message = "name_tag must not be empty."
  }
}

variable "tags" {
  description = "Tags applied to the CloudWatch log group."
  type        = map(string)
  default     = {}
}