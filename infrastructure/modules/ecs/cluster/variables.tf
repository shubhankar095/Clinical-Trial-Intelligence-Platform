variable "cluster_name" {
  description = "Name of the ECS cluster."
  type        = string
}

variable "container_insights_enabled" {
  description = "Whether ECS Container Insights is enabled."
  type        = bool
  default     = true
}

variable "tags" {
  description = "Tags applied to the ECS cluster."
  type        = map(string)
  default     = {}
}
