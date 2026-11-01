variable "task_family" {
  description = "Family name assigned to the ECS task definition."
  type        = string

  validation {
    condition     = length(trimspace(var.task_family)) > 0
    error_message = "task_family must not be empty."
  }
}

variable "service_name" {
  description = "Name assigned to the ECS service."
  type        = string

  validation {
    condition     = length(trimspace(var.service_name)) > 0
    error_message = "service_name must not be empty."
  }
}

variable "cluster_id" {
  description = "ID or ARN of the ECS cluster where the service runs."
  type        = string

  validation {
    condition     = length(trimspace(var.cluster_id)) > 0
    error_message = "cluster_id must not be empty."
  }
}

variable "cpu" {
  description = "CPU units assigned to the ECS task."
  type        = number

  validation {
    condition = contains(
      [
        256,
        512,
        1024,
        2048,
        4096,
        8192,
        16384
      ],
      var.cpu
    )

    error_message = "cpu must be a supported Fargate CPU value."
  }
}

variable "memory" {
  description = "Memory in MiB assigned to the ECS task."
  type        = number

  validation {
    condition     = var.memory > 0
    error_message = "memory must be greater than zero."
  }
}

variable "execution_role_arn" {
  description = "ARN of the ECS task execution IAM role."
  type        = string

  validation {
    condition     = length(trimspace(var.execution_role_arn)) > 0
    error_message = "execution_role_arn must not be empty."
  }
}

variable "task_role_arn" {
  description = "ARN of the IAM role used by application containers."
  type        = string

  validation {
    condition     = length(trimspace(var.task_role_arn)) > 0
    error_message = "task_role_arn must not be empty."
  }
}

variable "container_definitions_json" {
  description = "Rendered JSON containing the ECS container definitions."
  type        = string

  validation {
    condition = (
      length(trimspace(var.container_definitions_json)) > 0
      && can(jsondecode(var.container_definitions_json))
    )

    error_message = "container_definitions_json must contain valid, non-empty JSON."
  }
}

variable "desired_count" {
  description = "Initial desired number of ECS service tasks."
  type        = number

  validation {
    condition     = var.desired_count >= 0
    error_message = "desired_count must be zero or greater."
  }
}

variable "subnet_ids" {
  description = "Subnet IDs used by ECS tasks."
  type        = list(string)

  validation {
    condition     = length(var.subnet_ids) > 0
    error_message = "subnet_ids must contain at least one subnet ID."
  }
}

variable "security_group_ids" {
  description = "Security-group IDs assigned to ECS tasks."
  type        = list(string)

  validation {
    condition     = length(var.security_group_ids) > 0
    error_message = "security_group_ids must contain at least one security-group ID."
  }
}

variable "requires_compatibilities" {
  description = "ECS launch types required by the task definition."
  type        = list(string)

  default = [
    "FARGATE"
  ]
}

variable "network_mode" {
  description = "Docker networking mode used by the ECS task."
  type        = string
  default     = "awsvpc"
}

variable "operating_system_family" {
  description = "Operating-system family used by the ECS task."
  type        = string
  default     = "LINUX"
}

variable "cpu_architecture" {
  description = "CPU architecture used by the ECS task."
  type        = string
  default     = "X86_64"
}

variable "launch_type" {
  description = "Launch type used by the ECS service."
  type        = string
  default     = "FARGATE"
}

variable "deployment_minimum_healthy_percent" {
  description = "Minimum healthy-task percentage during an ECS deployment."
  type        = number
  default     = 0
}

variable "deployment_maximum_percent" {
  description = "Maximum task percentage allowed during an ECS deployment."
  type        = number
  default     = 100
}

variable "enable_execute_command" {
  description = "Whether ECS Exec is enabled for the service."
  type        = bool
  default     = true
}

variable "assign_public_ip" {
  description = "Whether ECS tasks receive public IP addresses."
  type        = bool
  default     = true
}

variable "tags" {
  description = "Tags applied to the ECS service."
  type        = map(string)
  default     = {}
}