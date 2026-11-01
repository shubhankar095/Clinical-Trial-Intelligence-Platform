variable "project_name" {
  description = "Project identifier used in names and tags."
  type        = string
  default     = "clinical-kb"

  validation {
    condition = (
      length(trimspace(var.project_name)) > 0
    )

    error_message = "project_name must not be empty."
  }
}

variable "aws_region" {
  description = "AWS region for the shared platform infrastructure."
  type        = string
  default     = "ap-south-1"

  validation {
    condition = (
      length(trimspace(var.aws_region)) > 0
    )

    error_message = "aws_region must not be empty."
  }
}

variable "environment" {
  description = "Deployment environment."
  type        = string
  default     = "dev"

  validation {
    condition = contains(
      [
        "dev",
        "uat",
        "stage",
        "prod"
      ],
      var.environment
    )

    error_message = "environment must be dev, uat, stage, or prod."
  }
}

variable "service_name" {
  description = "Service or platform package that owns the deployed resources."
  type        = string
  default     = "Platform"

  validation {
    condition = (
      length(trimspace(var.service_name)) > 0
    )

    error_message = "service_name must not be empty."
  }
}

variable "owner" {
  description = "Team accountable for the deployed resources."
  type        = string
  default     = "knowledge-base"

  validation {
    condition = (
      length(trimspace(var.owner)) > 0
    )

    error_message = "owner must not be empty."
  }
}

variable "vpc_cidr" {
  description = "CIDR block assigned to the shared VPC."
  type        = string

  validation {
    condition = (
      can(cidrnetmask(var.vpc_cidr))
    )

    error_message = "vpc_cidr must be a valid IPv4 CIDR block."
  }
}

variable "public_subnet_a_cidr" {
  description = "CIDR block assigned to the first public subnet."
  type        = string

  validation {
    condition = (
      can(cidrnetmask(var.public_subnet_a_cidr))
    )

    error_message = "public_subnet_a_cidr must be a valid IPv4 CIDR block."
  }
}

variable "public_subnet_b_cidr" {
  description = "CIDR block assigned to the second public subnet."
  type        = string

  validation {
    condition = (
      can(cidrnetmask(var.public_subnet_b_cidr))
    )

    error_message = "public_subnet_b_cidr must be a valid IPv4 CIDR block."
  }
}

variable "raw_bucket_name" {
  description = "Name of the shared raw-document bucket."
  type        = string

  validation {
    condition = (
      length(trimspace(var.raw_bucket_name)) > 0
    )

    error_message = "raw_bucket_name must not be empty."
  }
}

variable "canonical_bucket_name" {
  description = "Name of the shared canonical-document bucket."
  type        = string

  validation {
    condition = (
      length(trimspace(var.canonical_bucket_name)) > 0
    )

    error_message = "canonical_bucket_name must not be empty."
  }
}

variable "bucket_noncurrent_version_expiration_days" {
  description = "Days before noncurrent object versions expire."
  type        = number
  default     = 30

  validation {
    condition = (
      var.bucket_noncurrent_version_expiration_days >= 1
    )

    error_message = "bucket_noncurrent_version_expiration_days must be at least 1."
  }
}

variable "bucket_abort_incomplete_multipart_upload_days" {
  description = "Days before incomplete multipart uploads are aborted."
  type        = number
  default     = 7

  validation {
    condition = (
      var.bucket_abort_incomplete_multipart_upload_days >= 1
    )

    error_message = "bucket_abort_incomplete_multipart_upload_days must be at least 1."
  }
}

variable "ecs_container_insights_enabled" {
  description = "Whether Container Insights is enabled on the shared ECS cluster."
  type        = bool
  default     = true
}

variable "opensearch_collection_type" {
  description = "Type of the shared OpenSearch Serverless collection."
  type        = string
  default     = "VECTORSEARCH"

  validation {
    condition = contains(
      [
        "SEARCH",
        "TIMESERIES",
        "VECTORSEARCH"
      ],
      var.opensearch_collection_type
    )

    error_message = "opensearch_collection_type must be SEARCH, TIMESERIES, or VECTORSEARCH."
  }
}

variable "opensearch_collection_group_generation" {
  description = "Generation of the shared OpenSearch Serverless collection group."
  type        = string
  default     = "NEXTGEN"

  validation {
    condition = contains(
      [
        "CLASSIC",
        "NEXTGEN",
      ],
      var.opensearch_collection_group_generation
    )

    error_message = "opensearch_collection_group_generation must be CLASSIC or NEXTGEN."
  }
}

variable "opensearch_collection_group_standby_replicas" {
  description = "Whether standby replicas are enabled for the shared collection group."
  type        = string
  default     = "ENABLED"

  validation {
    condition = contains(
      [
        "ENABLED",
        "DISABLED",
      ],
      var.opensearch_collection_group_standby_replicas
    )

    error_message = "opensearch_collection_group_standby_replicas must be ENABLED or DISABLED."
  }

  validation {
    condition = (
      var.opensearch_collection_group_generation != "NEXTGEN"
      || var.opensearch_collection_group_standby_replicas == "ENABLED"
    )

    error_message = "NEXTGEN collection groups require standby replicas to be ENABLED."
  }
}

variable "opensearch_min_indexing_capacity_in_ocu" {
  description = "Minimum indexing capacity for the shared collection group."
  type        = number
  default     = 2

  validation {
    condition = contains(
      concat(
        [0, 2, 4, 8],
        [for value in range(16, 257, 16) : value]
      ),
      var.opensearch_min_indexing_capacity_in_ocu
    )

    error_message = "opensearch_min_indexing_capacity_in_ocu must be 0, 2, 4, 8, 16, or a multiple of 16."
  }
}

variable "opensearch_max_indexing_capacity_in_ocu" {
  description = "Maximum indexing capacity for the shared collection group."
  type        = number
  default     = 2

  validation {
    condition = contains(
      concat(
        [2, 4, 8],
        [for value in range(16, 257, 16) : value]
      ),
      var.opensearch_max_indexing_capacity_in_ocu
    )

    error_message = "opensearch_max_indexing_capacity_in_ocu must be 2, 4, 8, 16, or a multiple of 16."
  }

  validation {
    condition = (
      var.opensearch_max_indexing_capacity_in_ocu
      >= var.opensearch_min_indexing_capacity_in_ocu
    )

    error_message = "opensearch_max_indexing_capacity_in_ocu must be greater than or equal to opensearch_min_indexing_capacity_in_ocu."
  }
}

variable "opensearch_min_search_capacity_in_ocu" {
  description = "Minimum search capacity for the shared collection group."
  type        = number
  default     = 2

  validation {
    condition = contains(
      concat(
        [0, 2, 4, 8],
        [for value in range(16, 257, 16) : value]
      ),
      var.opensearch_min_search_capacity_in_ocu
    )

    error_message = "opensearch_min_search_capacity_in_ocu must be 0, 2, 4, 8, 16, or a multiple of 16."
  }
}

variable "opensearch_max_search_capacity_in_ocu" {
  description = "Maximum search capacity for the shared collection group."
  type        = number
  default     = 2

  validation {
    condition = contains(
      concat(
        [2, 4, 8],
        [for value in range(16, 257, 16) : value]
      ),
      var.opensearch_max_search_capacity_in_ocu
    )

    error_message = "opensearch_max_search_capacity_in_ocu must be 2, 4, 8, 16, or a multiple of 16."
  }

  validation {
    condition = (
      var.opensearch_max_search_capacity_in_ocu
      >= var.opensearch_min_search_capacity_in_ocu
    )

    error_message = "opensearch_max_search_capacity_in_ocu must be greater than or equal to opensearch_min_search_capacity_in_ocu."
  }
}

variable "opensearch_use_aws_owned_key" {
  description = "Whether OpenSearch Serverless encryption uses an AWS-owned key."
  type        = bool
  default     = true
}

variable "opensearch_kms_key_arn" {
  description = "Optional KMS key ARN used when AWS-owned encryption is disabled."
  type        = string
  default     = ""

  validation {
    condition = (
      var.opensearch_use_aws_owned_key
      || length(
        trimspace(
          var.opensearch_kms_key_arn
        )
      ) > 0
    )

    error_message = "opensearch_kms_key_arn is required when opensearch_use_aws_owned_key is false."
  }
}

variable "opensearch_allow_public_access" {
  description = "Whether the OpenSearch collection is reachable from public network sources."
  type        = bool
  default     = true
}

variable "opensearch_source_vpce_ids" {
  description = "OpenSearch Serverless VPC endpoint IDs allowed when public access is disabled."
  type        = list(string)
  default     = []

  validation {
    condition = (
      var.opensearch_allow_public_access
      || length(var.opensearch_source_vpce_ids) > 0
    )

    error_message = "opensearch_source_vpce_ids must not be empty when public access is disabled."
  }
}