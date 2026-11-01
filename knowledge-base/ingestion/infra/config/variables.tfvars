#-----------------------------------------------------
# Project and Environment
#-----------------------------------------------------
project_name = "clinical-kb"    # Project identifier used in resource names, tags, and metric namespaces.
aws_region   = "ap-south-1"     # AWS region where the Ingestion infrastructure is deployed.
environment  = "dev"            # Deployment environment: dev, uat, stage, or prod.
service_name = "Ingestion"      # Service identifier used in resource names, standard tags, and dashboard labels.
owner        = "knowledge-base" # Team accountable for the Ingestion infrastructure.


#-----------------------------------------------------
# Shared Platform Terraform State
#-----------------------------------------------------
platform_state_bucket = "tfstate-backend-config-dev"                # S3 bucket containing the shared Platform Terraform state.
platform_state_key    = "knowledge-base/platform/terraform.tfstate" # Object key of the Platform state consumed by Ingestion.
platform_state_region = "ap-south-1"                                # AWS region containing the Platform state bucket.

# The Platform state provides the shared VPC, public subnets,
# canonical bucket, and ECS cluster used by the Ingestion service.


#-----------------------------------------------------
# Container Image
#-----------------------------------------------------
image_tag = "dev" # ECR image tag deployed by the Ingestion ECS task definition.


#-----------------------------------------------------
# Alert Destination
#-----------------------------------------------------
alert_email = "shubhankar24x7@gmail.com" # Email subscribed to Ingestion alerts through Amazon SNS.


#-----------------------------------------------------
# Logging
#-----------------------------------------------------
log_retention_days = 30 # Number of days Ingestion logs are retained in CloudWatch Logs.


#-----------------------------------------------------
# ECS Worker Capacity and Sizing
#-----------------------------------------------------
ecs_min_capacity = 0 # Minimum worker count; zero enables scale-to-zero when the queue is idle.
ecs_max_capacity = 5 # Maximum number of Ingestion workers that can run concurrently.

ecs_cpu    = 1024 # CPU allocated to each Fargate worker; 1024 CPU units equal 1 vCPU.
ecs_memory = 2048 # Memory allocated to each Fargate worker in MiB; 2048 MiB equal 2 GiB.


#-----------------------------------------------------
# SQS Queue and Alarm Configuration
#-----------------------------------------------------
sqs_visibility_timeout_seconds = 600 # Initial message visibility timeout after an Ingestion worker receives a message.
sqs_max_receive_count          = 5   # Failed receives allowed before SQS moves a message to the dead-letter queue.
oldest_message_alarm_seconds   = 900 # Message age that triggers an alarm; 900 seconds equals 15 minutes.


#-----------------------------------------------------
# SQS Visibility Heartbeat
#-----------------------------------------------------
sqs_visibility_extension_seconds = 600 # Visibility timeout applied whenever an active message lease is renewed.
sqs_visibility_heartbeat_seconds = 180 # Interval between lease renewals; must be shorter than the Ingestion duration.


#-----------------------------------------------------
# Ingestion Schema and Chunking
#-----------------------------------------------------
ingestion_schema_version = "ingestion-v1" # Canonical schema version included in the processed-document identity.

chunker_type    = "page-aware-recursive-character"
chunker_version = "1"
chunk_size      = 1200
chunk_overlap   = 200


#-----------------------------------------------------
# Ingestion Result Manifests
#-----------------------------------------------------
ingestion_result_prefix = "ingestion-results"


#-----------------------------------------------------
# DynamoDB Processing Claim
#-----------------------------------------------------
processing_claim_lease_seconds     = 900 # Exclusive processing-claim duration; must exceed the visibility-renewal interval.
processing_claim_heartbeat_seconds = 300 # Interval between claim renewals; must be shorter than the claim lease.
processing_record_ttl_days         = 90

#-----------------------------------------------------
# OpenSearch Indexing
#-----------------------------------------------------
index_schema_version = "v1"

opensearch_deployment_type = "serverless"
opensearch_index_prefix    = "clinical-chunks"

opensearch_refresh_after_index = true
opensearch_bulk_max_records    = 250
opensearch_bulk_max_bytes      = 5242880
opensearch_bulk_max_attempts   = 3

# DAVV: Serverless skips explicit refresh and polls until the exact
# expected number of indexed records becomes searchable.
opensearch_visibility_timeout_seconds = 60
opensearch_visibility_poll_seconds    = 1


#-----------------------------------------------------
# Backlog-Based Autoscaling
#-----------------------------------------------------
backlog_per_task_target = 5 # Target number of visible SQS messages per running Ingestion worker.

ecs_scale_out_cooldown_seconds = 60  # Cooldown between target-tracking scale-out actions.
ecs_scale_in_cooldown_seconds  = 300 # Cooldown between target-tracking scale-in actions.


#-----------------------------------------------------
# Queue-Drained Scale-In
#-----------------------------------------------------
queue_drained_evaluation_periods        = 2  # Empty one-minute periods required before reducing excess workers to one.
queue_drained_scale_in_cooldown_seconds = 60 # Cooldown after excess workers are reduced directly to one.


#-----------------------------------------------------
# Final Scale to Zero
#-----------------------------------------------------
scale_to_zero_evaluation_periods    = 5   # Empty one-minute periods required before scaling the final worker to zero.
idle_scale_to_zero_cooldown_seconds = 300 # Cooldown after the final worker is scaled to zero.


#-----------------------------------------------------
# Embedding
#-----------------------------------------------------
embedding_provider   = "huggingface-api"
embedding_model_id   = "sentence-transformers/all-MiniLM-L6-v2"
embedding_dimensions = 384
embedding_normalize  = true

embedding_model_options = {}

huggingface_api_provider        = "hf-inference"
huggingface_api_base_url        = "https://router.huggingface.co" #"https://api-inference.huggingface.co"
huggingface_api_timeout_seconds = 60
huggingface_api_max_attempts    = 3
huggingface_api_token           = ""