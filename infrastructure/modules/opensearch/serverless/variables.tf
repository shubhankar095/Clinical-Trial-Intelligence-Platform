variable "collection_name" {
  description = "Name assigned to the OpenSearch Serverless collection."
  type        = string

  validation {
    condition = (
      length(
        trimspace(
          var.collection_name
        )
      ) > 0
    )

    error_message = "collection_name must not be empty."
  }
}

variable "collection_type" {
  description = "OpenSearch Serverless collection type."
  type        = string
  default     = "VECTORSEARCH"

  validation {
    condition = contains(
      [
        "SEARCH",
        "TIMESERIES",
        "VECTORSEARCH"
      ],
      var.collection_type
    )

    error_message = "collection_type must be SEARCH, TIMESERIES, or VECTORSEARCH."
  }
}

variable "description" {
  description = "Human-readable description of the collection."
  type        = string

  validation {
    condition = (
      length(
        trimspace(
          var.description
        )
      ) > 0
    )

    error_message = "description must not be empty."
  }
}

variable "use_aws_owned_key" {
  description = "Whether the collection encryption policy uses an AWS-owned key."
  type        = bool
  default     = true
}

variable "kms_key_arn" {
  description = "Optional customer-managed KMS key ARN used when use_aws_owned_key is false."
  type        = string
  default     = ""

  validation {
    condition = (
      var.use_aws_owned_key
      || length(
        trimspace(
          var.kms_key_arn
        )
      ) > 0
    )

    error_message = "kms_key_arn is required when use_aws_owned_key is false."
  }
}

variable "allow_public_access" {
  description = "Whether the collection and Dashboards are reachable from public network sources."
  type        = bool
  default     = false
}

variable "source_vpce_ids" {
  description = "OpenSearch Serverless VPC endpoint IDs allowed when public access is disabled."
  type        = list(string)
  default     = []

  validation {
    condition = (
      var.allow_public_access
      || length(var.source_vpce_ids) > 0
    )

    error_message = "source_vpce_ids must contain at least one endpoint when public access is disabled."
  }
}

variable "tags" {
  description = "Tags applied to supported OpenSearch Serverless resources."
  type        = map(string)
  default     = {}
}

variable "encryption_policy_name" {
  description = "Complete name assigned to the OpenSearch Serverless encryption policy."
  type        = string

  validation {
    condition = (
      length(
        trimspace(
          var.encryption_policy_name
        )
      ) > 0
    )

    error_message = "encryption_policy_name must not be empty."
  }
}

variable "network_policy_name" {
  description = "Complete name assigned to the OpenSearch Serverless network policy."
  type        = string

  validation {
    condition = (
      length(
        trimspace(
          var.network_policy_name
        )
      ) > 0
    )

    error_message = "network_policy_name must not be empty."
  }
}

variable "collection_group_name" {
  description = "Name assigned to the OpenSearch Serverless collection group."
  type        = string

  validation {
    condition = (
      length(trimspace(var.collection_group_name)) > 0
    )

    error_message = (
      "collection_group_name must not be empty."
    )
  }
}

variable "collection_group_generation" {
  description = "Generation of the OpenSearch Serverless collection group."
  type        = string
  default     = "NEXTGEN"

  validation {
    condition = contains(
      [
        "CLASSIC",
        "NEXTGEN",
      ],
      var.collection_group_generation
    )

    error_message = (
      "collection_group_generation must be CLASSIC or NEXTGEN."
    )
  }
}

variable "collection_group_standby_replicas" {
  description = "Whether standby replicas are enabled for the collection group."
  type        = string
  default     = "ENABLED"

  validation {
    condition = contains(
      [
        "ENABLED",
        "DISABLED",
      ],
      var.collection_group_standby_replicas
    )

    error_message = "collection_group_standby_replicas must be ENABLED or DISABLED."
  }

  validation {
    condition = (
      var.collection_group_generation != "NEXTGEN"
      || var.collection_group_standby_replicas == "ENABLED"
    )

    error_message = "NEXTGEN collection groups require standby replicas to be ENABLED."
  }
}

variable "min_indexing_capacity_in_ocu" {
  description = "Minimum indexing capacity allocated to the collection group."
  type        = number
  default     = 2

  validation {
    condition = contains(
      concat(
        [0, 2, 4, 8],
        [for value in range(16, 257, 16) : value]
      ),
      var.min_indexing_capacity_in_ocu
    )

    error_message = "min_indexing_capacity_in_ocu must be 0, 2, 4, 8, 16, or a multiple of 16."
  }
}

variable "max_indexing_capacity_in_ocu" {
  description = "Maximum indexing capacity allocated to the collection group."
  type        = number
  default     = 2

  validation {
    condition = contains(
      concat(
        [2, 4, 8],
        [for value in range(16, 257, 16) : value]
      ),
      var.max_indexing_capacity_in_ocu
    )

    error_message = "max_indexing_capacity_in_ocu must be 2, 4, 8, 16, or a multiple of 16."
  }
}

variable "min_search_capacity_in_ocu" {
  description = "Minimum search capacity allocated to the collection group."
  type        = number
  default     = 2

  validation {
    condition = contains(
      concat(
        [0, 2, 4, 8],
        [for value in range(16, 257, 16) : value]
      ),
      var.min_search_capacity_in_ocu
    )

    error_message = "min_search_capacity_in_ocu must be 0, 2, 4, 8, 16, or a multiple of 16."
  }
}

variable "max_search_capacity_in_ocu" {
  description = "Maximum search capacity allocated to the collection group."
  type        = number
  default     = 2

  validation {
    condition = contains(
      concat(
        [2, 4, 8],
        [for value in range(16, 257, 16) : value]
      ),
      var.max_search_capacity_in_ocu
    )

    error_message = "max_search_capacity_in_ocu must be 2, 4, 8, 16, or a multiple of 16."
  }
}