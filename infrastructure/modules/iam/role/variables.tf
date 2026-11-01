variable "role_name" {
  description = "Name assigned to the IAM role."
  type        = string

  validation {
    condition = (
      length(trimspace(var.role_name)) > 0
    )

    error_message = "role_name must not be empty."
  }
}

variable "trust_policy_json" {
  description = "Trust policy defining which principals may assume the IAM role."
  type        = string

  default = <<-JSON
  {
    "Version": "2012-10-17",
    "Statement": [
      {
        "Sid": "DefaultDenyAssumeRole",
        "Effect": "Deny",
        "Principal": {
          "AWS": "*"
        },
        "Action": "sts:AssumeRole"
      }
    ]
  }
  JSON

  validation {
    condition = (
      length(trimspace(var.trust_policy_json)) > 0
      && can(jsondecode(var.trust_policy_json))
    )

    error_message = "trust_policy_json must contain valid, non-empty JSON."
  }
}

variable "policy_arns" {
  description = "Managed IAM policy ARNs keyed by stable attachment identifiers."
  type        = map(string)
  default     = {}

  validation {
    condition = alltrue([
      for attachment_name, policy_arn in var.policy_arns :
      length(trimspace(attachment_name)) > 0
      && length(trimspace(policy_arn)) > 0
    ])

    error_message = "policy_arns must contain non-empty attachment names and policy ARNs."
  }
}

variable "tags" {
  description = "Optional tags applied to the IAM role."
  type        = map(string)
  default     = {}
}