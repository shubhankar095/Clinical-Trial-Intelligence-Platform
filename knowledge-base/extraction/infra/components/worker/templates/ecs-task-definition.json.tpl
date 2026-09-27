[
  {
    "name": "extraction",
    "image": "${image_uri}",
    "essential": true,
    "stopTimeout": 120,
    "healthCheck": {
      "command": [
        "CMD",
        "python",
        "-c",
        "import os; os.kill(1, 0)"
      ],
      "interval": 30,
      "timeout": 5,
      "retries": 3,
      "startPeriod": 60
    },
    "cpu": ${cpu},
    "memory": ${memory},

    "environment": [
      {
        "name": "AWS_DEFAULT_REGION",
        "value": "${region}"
      },
      {
        "name": "ENVIRONMENT",
        "value": "${environment}"
      },
      {
        "name": "DOCUMENT_UPLOADED_QUEUE_URL",
        "value": "${queue_url}"
      },
      {
        "name": "CANONICAL_DOCUMENT_BUCKET",
        "value": "${canonical_bucket}"
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
        "name": "PROCESSING_SCHEMA_VERSION",
        "value": "${processing_schema_version}"
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
