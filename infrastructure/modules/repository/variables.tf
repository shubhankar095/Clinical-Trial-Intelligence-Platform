variable "repository_name" {
  description = "Name assigned to the ECR repository."
  type        = string

  validation {
    condition     = length(trimspace(var.repository_name)) > 0
    error_message = "repository_name must not be empty."
  }
}

variable "force_delete" {
  description = "Whether Terraform can delete the repository when it contains images."
  type        = bool
  default     = false
}

variable "image_tag_mutability" {
  description = "Whether image tags in the repository are mutable or immutable."
  type        = string
  default     = "IMMUTABLE"

  validation {
    condition = contains(
      [
        "MUTABLE",
        "IMMUTABLE"
      ],
      var.image_tag_mutability
    )

    error_message = "image_tag_mutability must be MUTABLE or IMMUTABLE."
  }
}

variable "scan_on_push" {
  description = "Whether container images are scanned when pushed."
  type        = bool
  default     = true
}

variable "untagged_image_retention_days" {
  description = "Number of days untagged images remain before expiration."
  type        = number
  default     = 14

  validation {
    condition     = var.untagged_image_retention_days >= 1
    error_message = "untagged_image_retention_days must be at least 1."
  }
}

variable "tags" {
  description = "Tags applied to the ECR repository."
  type        = map(string)
  default     = {}
}