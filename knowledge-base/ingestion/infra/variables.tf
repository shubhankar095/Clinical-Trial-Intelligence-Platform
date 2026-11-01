variable "project_name" {
  description = "Project identifier used in names and tags."
  type        = string
  default     = "clinical-kb"
}

variable "aws_region" {
  description = "AWS region for the Ingestion service."
  type        = string
  default     = "ap-south-1"
}

variable "environment" {
  description = "Deployment environment."
  type        = string
  default     = "dev"

  validation {
    condition     = contains(["dev", "uat", "stage", "prod"], var.environment)
    error_message = "environment must be dev, uat, stage, or prod."
  }
}

variable "service_name" {
  description = "Service that owns the deployed resources."
  type        = string
  default     = "Ingestion"
}

variable "owner" {
  description = "Team accountable for the deployed resources."
  type        = string
  default     = "knowledge-base"
}

variable "platform_state_bucket" {
  description = "S3 bucket containing the Platform Terraform state."
  type        = string
}

variable "platform_state_key" {
  description = "S3 key containing the Platform Terraform state."
  type        = string
}

variable "platform_state_region" {
  description = "AWS region of the Platform Terraform state bucket."
  type        = string
}

variable "image_tag" {
  description = "ECR image tag deployed to the Ingestion ECS service"
  type        = string

  validation {
    condition = (
      length(trimspace(var.image_tag)) > 0
      && var.image_tag != "latest"
    )

    error_message = "image_tag must be non-empty and cannot be 'latest'."
  }

  validation {
    condition = (
      var.environment == "dev"
      || startswith(var.image_tag, "${var.environment}-")
      || (
        var.environment == "prod"
        && (
          startswith(var.image_tag, "v")
          || can(regex("^[0-9a-f]{7,40}$", var.image_tag))
        )
      )
    )

    error_message = "Use dev for development, environment-prefixed tags for UAT/stage, and a version or Git SHA for production."
  }
}

variable "alert_email" {
  description = "Email address subscribed to operational SNS alerts."
  type        = string
}

variable "log_retention_days" {
  description = "CloudWatch log retention in days."
  type        = number
  default     = 30
}

variable "ecs_min_capacity" {
  description = "Minimum ECS worker capacity."
  type        = number
  default     = 0

  validation {
    condition     = var.ecs_min_capacity >= 0
    error_message = "ecs_min_capacity must be zero or greater."
  }
}

variable "ecs_max_capacity" {
  description = "Maximum ECS worker capacity."
  type        = number
  default     = 5

  validation {
    condition     = var.ecs_max_capacity >= var.ecs_min_capacity
    error_message = "ecs_max_capacity must be greater than or equal to ecs_min_capacity."
  }
}

variable "ecs_cpu" {
  description = "ECS Fargate task CPU units"
  type        = number
  default     = 1024

  validation {
    condition = contains(
      [256, 512, 1024, 2048, 4096, 8192, 16384],
      var.ecs_cpu
    )

    error_message = "ecs_cpu must be a supported Fargate CPU value."
  }
}

variable "ecs_memory" {
  description = "ECS Fargate task memory in MiB"
  type        = number
  default     = 2048

  validation {
    condition     = var.ecs_memory > 0
    error_message = "ecs_memory must be greater than zero."
  }
}

variable "sqs_visibility_timeout_seconds" {
  description = "Initial visibility lease for a received Ingestion message"
  type        = number
  default     = 600

  validation {
    condition = (
      var.sqs_visibility_timeout_seconds > 0
      && var.sqs_visibility_timeout_seconds <= 43200
    )

    error_message = "sqs_visibility_timeout_seconds must be between 1 and 43200."
  }

  validation {
    condition = (
      var.sqs_visibility_timeout_seconds
      > var.sqs_visibility_heartbeat_seconds
    )

    error_message = "sqs_visibility_timeout_seconds must be greater than sqs_visibility_heartbeat_seconds."
  }
}

variable "sqs_max_receive_count" {
  description = "Number of failed receives before a message is moved to the DLQ"
  type        = number
  default     = 5

  validation {
    condition     = var.sqs_max_receive_count >= 1
    error_message = "sqs_max_receive_count must be at least 1."
  }
}

variable "oldest_message_alarm_seconds" {
  description = "Maximum acceptable age of the oldest visible Ingestion message"
  type        = number
  default     = 900

  validation {
    condition     = var.oldest_message_alarm_seconds > 0
    error_message = "oldest_message_alarm_seconds must be greater than zero."
  }
}

variable "sqs_visibility_extension_seconds" {
  description = "Visibility lease applied while document processing is active"
  type        = number
  default     = 600

  validation {
    condition = (
      var.sqs_visibility_extension_seconds > 0
      && var.sqs_visibility_extension_seconds <= 43200
    )

    error_message = "sqs_visibility_extension_seconds must be between 1 and 43200."
  }
}

variable "sqs_visibility_heartbeat_seconds" {
  description = "Interval between SQS visibility lease renewals"
  type        = number
  default     = 180

  validation {
    condition = (
      var.sqs_visibility_heartbeat_seconds > 0
      && (
        var.sqs_visibility_heartbeat_seconds
        < var.sqs_visibility_extension_seconds
      )
    )

    error_message = "sqs_visibility_heartbeat_seconds must be positive and less than sqs_visibility_extension_seconds."
  }
}

variable "ingestion_schema_version" {
  description = "Version of the Ingestion processing schema."
  type        = string
  default     = "ingestion-v1"

  validation {
    condition = (
      length(
        trimspace(
          var.ingestion_schema_version
        )
      ) > 0
    )

    error_message = "ingestion_schema_version must not be empty."
  }
}


variable "processing_claim_lease_seconds" {
  description = "Duration of an exclusive document-processing claim"
  type        = number
  default     = 1800

  validation {
    condition = (
      var.processing_claim_lease_seconds
      > var.sqs_visibility_extension_seconds
    )

    error_message = "processing_claim_lease_seconds must be greater than sqs_visibility_extension_seconds."
  }

  validation {
    condition = (
      var.processing_claim_lease_seconds
      <= 86400
    )

    error_message = "processing_claim_lease_seconds must not exceed 86400 seconds."
  }
}

variable "processing_claim_heartbeat_seconds" {
  description = "Interval between DynamoDB processing-claim lease renewals"
  type        = number
  default     = 300

  validation {
    condition = (
      var.processing_claim_heartbeat_seconds > 0
      && (
        var.processing_claim_heartbeat_seconds
        < var.processing_claim_lease_seconds
      )
    )

    error_message = "processing_claim_heartbeat_seconds must be positive and less than processing_claim_lease_seconds."
  }
}

variable "backlog_per_task_target" {
  description = "Target number of visible SQS messages per running Ingestion task"
  type        = number
  default     = 5

  validation {
    condition = (
      var.backlog_per_task_target > 0
    )

    error_message = "backlog_per_task_target must be greater than zero."
  }
}

variable "ecs_scale_out_cooldown_seconds" {
  description = "Seconds before another backlog-based scale-out evaluation"
  type        = number
  default     = 60

  validation {
    condition = (
      var.ecs_scale_out_cooldown_seconds >= 0
      && var.ecs_scale_out_cooldown_seconds <= 3600
    )

    error_message = "ecs_scale_out_cooldown_seconds must be between 0 and 3600."
  }
}

variable "ecs_scale_in_cooldown_seconds" {
  description = "Seconds between proportional backlog-based target-tracking scale-in actions"
  type        = number
  default     = 300

  validation {
    condition = (
      var.ecs_scale_in_cooldown_seconds >= 0
      && var.ecs_scale_in_cooldown_seconds <= 3600
    )

    error_message = "ecs_scale_in_cooldown_seconds must be between 0 and 3600."
  }
}

variable "queue_drained_evaluation_periods" {
  description = "Consecutive one-minute empty queue periods required before reducing excess Ingestion workers directly to one"
  type        = number
  default     = 2

  validation {
    condition = (
      var.queue_drained_evaluation_periods >= 1
      && var.queue_drained_evaluation_periods < var.scale_to_zero_evaluation_periods
    )

    error_message = "queue_drained_evaluation_periods must be at least 1 and less than scale_to_zero_evaluation_periods."
  }
}

variable "queue_drained_scale_in_cooldown_seconds" {
  description = "Cooldown after reducing excess Ingestion workers directly to one"
  type        = number
  default     = 60

  validation {
    condition = (
      var.queue_drained_scale_in_cooldown_seconds >= 0
      && var.queue_drained_scale_in_cooldown_seconds <= 3600
    )

    error_message = "queue_drained_scale_in_cooldown_seconds must be between 0 and 3600."
  }
}

variable "scale_to_zero_evaluation_periods" {
  description = "Consecutive one-minute empty queue periods required before reducing the final Ingestion worker to zero"
  type        = number
  default     = 5

  validation {
    condition = (
      var.scale_to_zero_evaluation_periods >= 5
      && var.scale_to_zero_evaluation_periods <= 60
    )

    error_message = "scale_to_zero_evaluation_periods must be between 5 and 60."
  }
}

variable "idle_scale_to_zero_cooldown_seconds" {
  description = "Cooldown after reducing the final Ingestion worker to zero"
  type        = number
  default     = 300

  validation {
    condition = (
      var.idle_scale_to_zero_cooldown_seconds >= 0
      && var.idle_scale_to_zero_cooldown_seconds <= 3600
    )

    error_message = "idle_scale_to_zero_cooldown_seconds must be between 0 and 3600."
  }
}

variable "ingestion_result_prefix" {
  description = "Canonical-bucket prefix used for Ingestion result manifests."
  type        = string
  default     = "ingestion-results"

  validation {
    condition = (
      length(
        trimspace(
          var.ingestion_result_prefix
        )
      ) > 0
    )

    error_message = "ingestion_result_prefix must not be empty."
  }
}

variable "processing_record_ttl_days" {
  description = "Number of days completed and failed processing records remain in DynamoDB."
  type        = number
  default     = 90

  validation {
    condition = (
      var.processing_record_ttl_days > 0
      && var.processing_record_ttl_days <= 3650
    )

    error_message = "processing_record_ttl_days must be between 1 and 3650."
  }
}

variable "chunker_type" {
  description = "Chunker implementation used by Ingestion."
  type        = string
  default     = "page-aware-recursive-character"
}

variable "chunker_version" {
  description = "Version of the configured chunking behavior."
  type        = string
  default     = "1"
}

variable "chunk_size" {
  description = "Target chunk size in characters."
  type        = number
  default     = 1200

  validation {
    condition     = var.chunk_size > 0
    error_message = "chunk_size must be greater than zero."
  }
}

variable "chunk_overlap" {
  description = "Character overlap between adjacent chunks."
  type        = number
  default     = 200

  validation {
    condition = (
      var.chunk_overlap >= 0
      && var.chunk_overlap < var.chunk_size
    )

    error_message = "chunk_overlap must be nonnegative and less than chunk_size."
  }
}

variable "index_schema_version" {
  description = "Version of the OpenSearch record schema."
  type        = string
  default     = "v1"

  validation {
    condition = (
      length(
        trimspace(
          var.index_schema_version
        )
      ) > 0
    )

    error_message = "index_schema_version must not be empty."
  }
}

variable "opensearch_deployment_type" {
  description = "OpenSearch deployment type used by Ingestion."
  type        = string
  default     = "serverless"

  validation {
    condition = (
      lower(
        trimspace(
          var.opensearch_deployment_type
        )
      ) == "serverless"
    )

    error_message = "This Terraform root supports only OpenSearch Serverless."
  }
}


variable "opensearch_index_prefix" {
  description = "Prefix used for profile-specific OpenSearch indexes."
  type        = string
  default     = "clinical-chunks"

  validation {
    condition = (
      length(
        trimspace(
          var.opensearch_index_prefix
        )
      ) > 0
    )

    error_message = "opensearch_index_prefix must not be empty."
  }
}

variable "opensearch_refresh_after_index" {
  description = "Whether OpenSearch is refreshed before final record-count verification."
  type        = bool
  default     = true
}

variable "opensearch_bulk_max_records" {
  description = "Maximum number of records in one OpenSearch bulk request."
  type        = number
  default     = 250

  validation {
    condition = (
      var.opensearch_bulk_max_records > 0
    )

    error_message = "opensearch_bulk_max_records must be greater than zero."
  }
}

variable "opensearch_bulk_max_bytes" {
  description = "Approximate maximum bytes allowed in one OpenSearch bulk request."
  type        = number
  default     = 5242880

  validation {
    condition = (
      var.opensearch_bulk_max_bytes > 0
    )

    error_message = "opensearch_bulk_max_bytes must be greater than zero."
  }
}

variable "opensearch_bulk_max_attempts" {
  description = "Maximum attempts for retryable OpenSearch bulk operations."
  type        = number
  default     = 3

  validation {
    condition = (
      var.opensearch_bulk_max_attempts >= 1
    )

    error_message = "opensearch_bulk_max_attempts must be at least one."
  }
}

variable "opensearch_visibility_timeout_seconds" {
  description = "Maximum time DAVV waits for indexed OpenSearch records to become searchable."
  type        = number
  default     = 60

  validation {
    condition = (
      var.opensearch_visibility_timeout_seconds > 0
      && var.opensearch_visibility_timeout_seconds <= 600
    )

    error_message = "opensearch_visibility_timeout_seconds must be greater than zero and no more than 600 seconds."
  }
}

variable "opensearch_visibility_poll_seconds" {
  description = "Interval between DAVV OpenSearch record-count visibility checks."
  type        = number
  default     = 1

  validation {
    condition = (
      var.opensearch_visibility_poll_seconds > 0
      && (
        var.opensearch_visibility_poll_seconds
        <= var.opensearch_visibility_timeout_seconds
      )
    )

    error_message = "opensearch_visibility_poll_seconds must be greater than zero and no more than opensearch_visibility_timeout_seconds."
  }
}

variable "embedding_provider" {
  description = "Embedding provider used by ingestion."
  type        = string
}

variable "embedding_model_id" {
  description = "Embedding model identifier."
  type        = string
}

variable "embedding_dimensions" {
  description = "Expected embedding vector dimensions."
  type        = number
}

variable "embedding_normalize" {
  description = "Whether produced embeddings are normalized."
  type        = bool
}

variable "embedding_model_options" {
  description = "Provider specific model options."
  type        = map(any)
  default     = {}
}

variable "huggingface_api_provider" {
  description = "Hugging Face inference provider."
  type        = string
  default     = "hf-inference"
}

variable "huggingface_api_base_url" {
  description = "Hugging Face inference API endpoint."
  type        = string
  default     = "https://api-inference.huggingface.co"
}

variable "huggingface_api_timeout_seconds" {
  description = "Hugging Face request timeout."
  type        = number
  default     = 60
}

variable "huggingface_api_max_attempts" {
  description = "Maximum Hugging Face retry attempts."
  type        = number
  default     = 3
}

variable "huggingface_api_token" {
  description = "Hugging Face API token"
  type        = string
  sensitive   = true
}