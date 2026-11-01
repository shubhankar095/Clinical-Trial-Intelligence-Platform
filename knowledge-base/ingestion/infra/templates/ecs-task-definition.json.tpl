[
  {
    "name": "ingestion",
    "image": "${image_uri}",
    "essential": true,
    "stopTimeout": 120,
    "healthCheck": {
      "command": ["CMD", "python", "-c", "import os; os.kill(1, 0)"],
      "interval": 30,
      "timeout": 5,
      "retries": 3,
      "startPeriod": 60
    },
    "cpu": ${cpu},
    "memory": ${memory},
    "environment": [

      {"name": "AWS_DEFAULT_REGION", "value": "${region}"},
      {"name": "AWS_REGION", "value": "${region}" },
      {"name": "ENVIRONMENT","value": "${environment}" },
      {"name": "INGESTION_QUEUE_URL", "value": "${queue_url}" },
      {"name": "CANONICAL_DOCUMENT_BUCKET", "value": "${canonical_bucket}"},
      {
        "name": "INGESTION_RESULT_BUCKET",
        "value": "${result_bucket}"
      },
      {
        "name": "INGESTION_RESULT_PREFIX",
        "value": "${result_prefix}"
      },
      {
        "name": "SQS_WAIT_TIME_SECONDS",
        "value": "${sqs_wait_time_seconds}"
      },
      {
        "name": "SQS_VISIBILITY_TIMEOUT_SECONDS",
        "value": "${visibility_timeout_seconds}"
      },
      {
        "name": "SQS_VISIBILITY_EXTENSION_SECONDS",
        "value": "${visibility_extension_seconds}"
      },
      {
        "name": "SQS_VISIBILITY_HEARTBEAT_SECONDS",
        "value": "${visibility_heartbeat_seconds}"
      },
      {
        "name": "PROCESSING_REGISTRY_TABLE",
        "value": "${processing_registry_table}"
      },
      {
        "name": "PROCESSING_CLAIM_LEASE_SECONDS",
        "value": "${processing_claim_lease_seconds}"
      },
      {
        "name": "PROCESSING_CLAIM_HEARTBEAT_SECONDS",
        "value": "${processing_claim_heartbeat_seconds}"
      },
      {
        "name": "PROCESSING_RECORD_TTL_DAYS",
        "value": "${processing_record_ttl_days}"
      },
      {
        "name": "INGESTION_SCHEMA_VERSION",
        "value": "${ingestion_schema_version}"
      },
      {
        "name": "CHUNKER_TYPE",
        "value": "${chunker_type}"
      },
      {
        "name": "CHUNKER_VERSION",
        "value": "${chunker_version}"
      },
      {
        "name": "CHUNK_SIZE",
        "value": "${chunk_size}"
      },
      {
        "name": "CHUNK_OVERLAP",
        "value": "${chunk_overlap}"
      },
      {
        "name": "EMBEDDING_PROVIDER",
        "value": "${embedding_provider}"
      },
      {
        "name": "EMBEDDING_MODEL_ID",
        "value": "${embedding_model_id}"
      },
      {
        "name": "EMBEDDING_DIMENSIONS",
        "value": "${embedding_dimensions}"
      },
      {
        "name": "EMBEDDING_NORMALIZE",
        "value": "${embedding_normalize}"
      },
      {
        "name": "EMBEDDING_MODEL_OPTIONS",
        "value": "${embedding_model_options}"
      },
      {
        "name": "HUGGINGFACE_API_PROVIDER",
        "value": "${huggingface_api_provider}"
      },
      {
        "name": "HUGGINGFACE_API_BASE_URL",
        "value": "${huggingface_api_base_url}"
      },
      {
        "name": "HUGGINGFACE_API_TIMEOUT_SECONDS",
        "value": "${huggingface_api_timeout_seconds}"
      },
      {
        "name": "HUGGINGFACE_API_MAX_ATTEMPTS",
        "value": "${huggingface_api_max_attempts}"
      },
      {
        "name": "HUGGINGFACE_API_TOKEN",
        "value": "${huggingface_api_token}"
      },
      {
        "name": "INDEX_SCHEMA_VERSION",
        "value": "${index_schema_version}"
      },
      {
        "name": "OPENSEARCH_DEPLOYMENT_TYPE",
        "value": "${opensearch_deployment_type}"
      },
      {
        "name": "OPENSEARCH_ENDPOINT",
        "value": "${opensearch_endpoint}"
      },
      {
        "name": "OPENSEARCH_REGION",
        "value": "${opensearch_region}"
      },
      {
        "name": "OPENSEARCH_INDEX_PREFIX",
        "value": "${opensearch_index_prefix}"
      },
      {
        "name": "OPENSEARCH_REFRESH_AFTER_INDEX",
        "value": "${opensearch_refresh_after_index}"
      },
      {
        "name": "OPENSEARCH_BULK_MAX_RECORDS",
        "value": "${opensearch_bulk_max_records}"
      },
      {
        "name": "OPENSEARCH_BULK_MAX_BYTES",
        "value": "${opensearch_bulk_max_bytes}"
      },
      {
        "name": "OPENSEARCH_BULK_MAX_ATTEMPTS",
        "value": "${opensearch_bulk_max_attempts}"
      },
      {
        "name": "OPENSEARCH_VISIBILITY_TIMEOUT_SECONDS",
        "value": "${opensearch_visibility_timeout_seconds}"
      },
      {
        "name": "OPENSEARCH_VISIBILITY_POLL_SECONDS",
        "value": "${opensearch_visibility_poll_seconds}"
      },
      {
        "name": "LOG_FORMAT",
        "value": "json"
      },
      {
        "name": "LOG_LEVEL",
        "value": "info"
      }
    ],
    "logConfiguration": {
      "logDriver": "awslogs",
      "options": {
        "awslogs-group": "${log_group}",
        "awslogs-region": "${region}",
        "awslogs-stream-prefix": "ecs"
      }
    }
  }
]
