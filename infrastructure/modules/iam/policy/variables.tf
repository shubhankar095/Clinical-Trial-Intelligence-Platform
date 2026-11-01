variable "policy_name" {
  description = "Name assigned to the customer-managed IAM policy."
  type        = string

  validation {
    condition     = length(trimspace(var.policy_name)) > 0
    error_message = "policy_name must not be empty."
  }
}

variable "policy_json" {
  description = "Rendered customer-managed IAM permissions policy JSON."
  type        = string

  validation {
    condition = (
      length(trimspace(var.policy_json)) > 0
      && can(jsondecode(var.policy_json))
    )

    error_message = "policy_json must contain valid, non-empty JSON."
  }
}

variable "tags" {
  description = "Optional tags applied to the IAM policy."
  type        = map(string)
  default     = {}
}