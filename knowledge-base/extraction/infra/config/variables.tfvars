#-----------------------------------------------------
# Project and Environment
#-----------------------------------------------------
project_name = "clinical-kb" # Project identifier used in resource names, tags, and metric namespaces.
aws_region   = "ap-south-1"  # AWS region where the extraction infrastructure is deployed.
environment  = "dev"         # Deployment environment: dev, uat, stage, or prod.


#-----------------------------------------------------
# Document Storage
#-----------------------------------------------------
raw_bucket_name       = "clinical-kb-raw-dev"       # S3 bucket containing uploaded source documents.
canonical_bucket_name = "clinical-kb-canonical-dev" # S3 bucket containing extracted documents and assets.


#-----------------------------------------------------
# ECS Worker Capacity
#-----------------------------------------------------
ecs_min_capacity = 0 # Minimum worker count; zero enables scale-to-zero when idle.
ecs_max_capacity = 5 # Maximum number of extraction workers that can run concurrently.

ecs_cpu    = 1024 # CPU allocated to each Fargate worker; 1024 units equal 1 vCPU.
ecs_memory = 2048 # Memory allocated to each Fargate worker in MiB; 2048 MiB equal 2 GiB.

image_tag = "dev" # ECR image tag deployed by the ECS task definition.


#-----------------------------------------------------
# Logging, Queue, and Alarms
#-----------------------------------------------------
log_retention_days             = 30  # Number of days extraction logs are retained in CloudWatch.
sqs_visibility_timeout_seconds = 600 # Initial SQS message visibility timeout in seconds.
sqs_max_receive_count          = 5   # Failed receives allowed before a message moves to the DLQ.
oldest_message_alarm_seconds   = 900 # Message age that triggers an alarm; 900 seconds equals 15 minutes.


#-----------------------------------------------------
# Network
#-----------------------------------------------------
vpc_cidr             = "10.0.0.0/16" # CIDR range assigned to the extraction VPC.
public_subnet_a_cidr = "10.0.1.0/24" # CIDR range assigned to the first public subnet.
public_subnet_b_cidr = "10.0.2.0/24" # CIDR range assigned to the second public subnet.


#-----------------------------------------------------
# SQS Visibility Heartbeat
#-----------------------------------------------------
sqs_visibility_extension_seconds = 600 # Visibility timeout applied when an active message lease is renewed.
sqs_visibility_heartbeat_seconds = 180 # Interval between renewals; must be shorter than the extension duration.


#-----------------------------------------------------
# Processing Schema
#-----------------------------------------------------
processing_schema_version = "extraction-v1" # Canonical schema version included in the document identity.


#-----------------------------------------------------
# DynamoDB Processing Claim
#-----------------------------------------------------
processing_claim_lease_seconds     = 900 # Exclusive processing-claim duration; must exceed SQS visibility extension.
processing_claim_heartbeat_seconds = 5   # Claim renewal interval; must be shorter than the claim lease.


#-----------------------------------------------------
# Backlog-Based Autoscaling
#-----------------------------------------------------
backlog_per_task_target = 5 # Target number of visible SQS messages per running worker.

ecs_scale_out_cooldown_seconds = 60  # Cooldown between target-tracking scale-out actions.
ecs_scale_in_cooldown_seconds  = 300 # Cooldown between target-tracking scale-in actions.


#-----------------------------------------------------
# Queue-Drained Scale-In
#-----------------------------------------------------
queue_drained_evaluation_periods        = 2  # Empty one-minute periods required before reducing workers to one.
queue_drained_scale_in_cooldown_seconds = 60 # Cooldown after excess workers are reduced to one.


#-----------------------------------------------------
# Final Scale to Zero
#-----------------------------------------------------
scale_to_zero_evaluation_periods    = 5   # Idle one-minute periods required before scaling the final worker to zero.
idle_scale_to_zero_cooldown_seconds = 300 # Cooldown after the final worker is scaled to zero.


#-----------------------------------------------------
# Alert Destination
#-----------------------------------------------------
alert_email = "shubhankar24x7@gmail.com" # Email subscribed to extraction alerts through Amazon SNS.





