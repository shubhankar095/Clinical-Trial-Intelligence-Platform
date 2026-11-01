#-----------------------------------------------------
# Project and Environment
#-----------------------------------------------------
project_name = "clinical-kb"    # Project identifier used in resource names, tags, and metric namespaces.
aws_region   = "ap-south-1"     # AWS region where the Extraction infrastructure is deployed.
environment  = "dev"            # Deployment environment: dev, uat, stage, or prod.
service_name = "Extraction"     # Service identifier used in resource names, standard tags, and dashboard labels.
owner        = "knowledge-base" # Team accountable for the Extraction infrastructure.


#-----------------------------------------------------
# Shared Platform Terraform State
#-----------------------------------------------------
platform_state_bucket = "tfstate-backend-config-dev"                # S3 bucket containing the shared Platform Terraform state.
platform_state_key    = "knowledge-base/platform/terraform.tfstate" # Object key of the Platform state consumed by Extraction.
platform_state_region = "ap-south-1"                                # AWS region containing the Platform state bucket.

# The Platform state provides the shared VPC, public subnets, raw bucket,
# canonical bucket, and ECS cluster used by the Extraction service.


#-----------------------------------------------------
# Container Image
#-----------------------------------------------------
image_tag = "dev" # ECR image tag deployed by the Extraction ECS task definition.


#-----------------------------------------------------
# Alert Destination
#-----------------------------------------------------
alert_email = "shubhankar24x7@gmail.com" # Email subscribed to Extraction alerts through Amazon SNS.


#-----------------------------------------------------
# Logging
#-----------------------------------------------------
log_retention_days = 30 # Number of days Extraction logs are retained in CloudWatch Logs.


#-----------------------------------------------------
# ECS Worker Capacity and Sizing
#-----------------------------------------------------
ecs_min_capacity = 0 # Minimum worker count; zero enables scale-to-zero when the queue is idle.
ecs_max_capacity = 5 # Maximum number of Extraction workers that can run concurrently.

ecs_cpu    = 1024 # CPU allocated to each Fargate worker; 1024 CPU units equal 1 vCPU.
ecs_memory = 2048 # Memory allocated to each Fargate worker in MiB; 2048 MiB equal 2 GiB.


#-----------------------------------------------------
# SQS Queue and Alarm Configuration
#-----------------------------------------------------
sqs_visibility_timeout_seconds = 600 # Initial message visibility timeout after an Extraction worker receives a message.
sqs_max_receive_count          = 5   # Failed receives allowed before SQS moves a message to the dead-letter queue.
oldest_message_alarm_seconds   = 900 # Message age that triggers an alarm; 900 seconds equals 15 minutes.


#-----------------------------------------------------
# SQS Visibility Heartbeat
#-----------------------------------------------------
sqs_visibility_extension_seconds = 600 # Visibility timeout applied whenever an active message lease is renewed.
sqs_visibility_heartbeat_seconds = 180 # Interval between lease renewals; must be shorter than the extension duration.


#-----------------------------------------------------
# Processing Schema
#-----------------------------------------------------
processing_schema_version = "extraction-v1" # Canonical schema version included in the processed-document identity.


#-----------------------------------------------------
# DynamoDB Processing Claim
#-----------------------------------------------------
processing_claim_lease_seconds     = 900 # Exclusive processing-claim duration; must exceed the visibility-renewal interval.
processing_claim_heartbeat_seconds = 5   # Interval between claim renewals; must be shorter than the claim lease.


#-----------------------------------------------------
# Backlog-Based Autoscaling
#-----------------------------------------------------
backlog_per_task_target = 5 # Target number of visible SQS messages per running Extraction worker.

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