project_name = "clinical-kb"
aws_region   = "ap-south-1"
environment  = "dev"

service_name = "Platform"
owner        = "knowledge-base"

vpc_cidr             = "10.0.0.0/16"
public_subnet_a_cidr = "10.0.1.0/24"
public_subnet_b_cidr = "10.0.2.0/24"

raw_bucket_name       = "clinical-kb-raw-dev"
canonical_bucket_name = "clinical-kb-processed-dev"

bucket_noncurrent_version_expiration_days     = 30
bucket_abort_incomplete_multipart_upload_days = 7

ecs_container_insights_enabled = true

#-----------------------------------------------------
# OpenSearch Serverless
#-----------------------------------------------------
opensearch_collection_type = "VECTORSEARCH"

# NextGen is required for the custom document-ID capability test.
opensearch_collection_group_generation = "NEXTGEN"

# NextGen collection groups require standby replicas.
opensearch_collection_group_standby_replicas = "ENABLED"

# Conservative development capacity limits for the capability test.
opensearch_min_indexing_capacity_in_ocu = 2
opensearch_max_indexing_capacity_in_ocu = 2
opensearch_min_search_capacity_in_ocu   = 2
opensearch_max_search_capacity_in_ocu   = 2

# Development uses an AWS-owned encryption key.
opensearch_use_aws_owned_key = true
opensearch_kms_key_arn       = ""

# Development ECS tasks use public subnets and public IP addresses.
# Authentication and data authorization are still enforced separately.
opensearch_allow_public_access = true
opensearch_source_vpce_ids     = []