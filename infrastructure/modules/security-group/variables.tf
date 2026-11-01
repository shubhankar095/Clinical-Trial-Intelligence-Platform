variable "security_group_name" {
  description = "Name assigned to the security group."
  type        = string

  validation {
    condition = (
      length(trimspace(var.security_group_name)) > 0
    )

    error_message = "security_group_name must not be empty."
  }
}

variable "description" {
  description = "Description assigned to the security group."
  type        = string

  validation {
    condition = (
      length(trimspace(var.description)) > 0
    )

    error_message = "description must not be empty."
  }
}

variable "vpc_id" {
  description = "ID of the VPC where the security group is created."
  type        = string

  validation {
    condition = (
      length(trimspace(var.vpc_id)) > 0
    )

    error_message = "vpc_id must not be empty."
  }
}

variable "egress_ipv4_cidr_blocks" {
  description = "IPv4 CIDR blocks allowed for outbound traffic."
  type        = list(string)

  default = [
    "0.0.0.0/0"
  ]

  validation {
    condition = (
      length(var.egress_ipv4_cidr_blocks) > 0
    )

    error_message = "egress_ipv4_cidr_blocks must contain at least one CIDR block."
  }
}

variable "tags" {
  description = "Tags applied to the security group."
  type        = map(string)
  default     = {}
}