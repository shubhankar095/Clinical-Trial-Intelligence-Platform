module "network" {
  source = "../modules/network"

  vpc_name                = local.names.vpc
  internet_gateway_name   = local.names.internet_gateway
  public_route_table_name = local.names.public_route_table
  vpc_cidr                = var.vpc_cidr

  public_subnets = {
    a = {
      name                    = local.names.public_subnet_a
      cidr_block              = var.public_subnet_a_cidr
      availability_zone_index = 0
    }

    b = {
      name                    = local.names.public_subnet_b
      cidr_block              = var.public_subnet_b_cidr
      availability_zone_index = 1
    }
  }

  enable_dns_support      = true
  enable_dns_hostnames    = true
  map_public_ip_on_launch = true
}

module "raw_bucket" {
  source = "../modules/s3-data-bucket"

  bucket_name   = var.raw_bucket_name
  force_destroy = var.environment == "dev"

  versioning_enabled = true
  lifecycle_rule_id  = "cleanup-noncurrent-raw-versions"

  noncurrent_version_expiration_days = (
    var.bucket_noncurrent_version_expiration_days
  )

  abort_incomplete_multipart_upload_days = (
    var.bucket_abort_incomplete_multipart_upload_days
  )
}

module "canonical_bucket" {
  source = "../modules/s3-data-bucket"

  bucket_name   = var.canonical_bucket_name
  force_destroy = var.environment == "dev"

  versioning_enabled = true
  lifecycle_rule_id  = "cleanup-noncurrent-canonical-versions"

  noncurrent_version_expiration_days = (
    var.bucket_noncurrent_version_expiration_days
  )

  abort_incomplete_multipart_upload_days = (
    var.bucket_abort_incomplete_multipart_upload_days
  )
}

module "ecs_cluster" {
  source = "../modules/ecs/cluster"

  cluster_name = local.names.ecs_cluster

  container_insights_enabled = (
    var.ecs_container_insights_enabled
  )
}


module "opensearch_serverless" {
  source = "../modules/opensearch/serverless"

  collection_name = local.names.opensearch_collection
  collection_type = var.opensearch_collection_type

  description = "Shared knowledge-base vector-search collection for ${var.environment}"

  collection_group_name = local.names.opensearch_collection_group

  collection_group_generation = var.opensearch_collection_group_generation

  collection_group_standby_replicas = var.opensearch_collection_group_standby_replicas

  min_indexing_capacity_in_ocu = var.opensearch_min_indexing_capacity_in_ocu

  max_indexing_capacity_in_ocu = var.opensearch_max_indexing_capacity_in_ocu

  min_search_capacity_in_ocu = var.opensearch_min_search_capacity_in_ocu

  max_search_capacity_in_ocu = var.opensearch_max_search_capacity_in_ocu

  encryption_policy_name = local.names.opensearch_encryption_policy

  network_policy_name = local.names.opensearch_network_policy

  use_aws_owned_key = var.opensearch_use_aws_owned_key

  kms_key_arn = var.opensearch_kms_key_arn

  allow_public_access = var.opensearch_allow_public_access

  source_vpce_ids = var.opensearch_source_vpce_ids
}