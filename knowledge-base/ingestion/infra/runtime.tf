# -----------------------------------------------------------------------------
# IAM permissions
# -----------------------------------------------------------------------------

module "ingestion_permissions" {
  source = "../../../infrastructure/modules/iam/policy"

  policy_name = local.names.permissions_policy

  policy_json = templatefile(
    "${path.module}/templates/ingestion-permissions-policy.json.tpl",
    {
      canonical_bucket           = local.platform.canonical_bucket_name
      result_bucket              = local.platform.canonical_bucket_name
      result_prefix              = var.ingestion_result_prefix
      queue_arn                  = module.ingestion_queue.queue_arn
      processing_registry_arn    = module.ingestion_registry.table_arn
      opensearch_deployment_type = var.opensearch_deployment_type
      opensearch_resource_arn    = local.platform.opensearch_collection_arn

    }
  )
}

module "ingestion_task_role" {
  source = "../../../infrastructure/modules/iam/role"

  role_name = local.names.task_role

  trust_policy_json = templatefile(
    "${path.module}/templates/ingestion-trust-policy.json.tpl",
    {}
  )

  policy_arns = {
    task_permissions = module.ingestion_permissions.policy_arn
  }
}

module "ingestion_execution_role" {
  source = "../../../infrastructure/modules/iam/role"

  role_name = local.names.execution_role

  trust_policy_json = templatefile(
    "${path.module}/templates/ingestion-trust-policy.json.tpl",
    {}
  )

  policy_arns = {
    ecs_task_execution = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
  }
}

# -----------------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------------

module "ingestion_logs" {
  source = "../../../infrastructure/modules/observability/logs"

  log_group_name    = local.names.log_group
  retention_in_days = var.log_retention_days
  name_tag          = local.names.log_group_name_tag
}

# -----------------------------------------------------------------------------
# ECS worker
# -----------------------------------------------------------------------------

module "ingestion_worker" {
  source = "../../../infrastructure/modules/ecs/worker"

  task_family  = local.names.task_family
  service_name = local.names.ecs_service
  cluster_id   = local.platform.ecs_cluster_id

  cpu    = var.ecs_cpu
  memory = var.ecs_memory

  execution_role_arn = module.ingestion_execution_role.role_arn
  task_role_arn      = module.ingestion_task_role.role_arn

  container_definitions_json = templatefile(
    "${path.module}/templates/ecs-task-definition.json.tpl",
    {
      image_uri   = "${module.ingestion_repository.repository_url}:${var.image_tag}"
      log_group   = module.ingestion_logs.log_group_name
      region      = var.aws_region
      environment = var.environment

      queue_url        = module.ingestion_queue.queue_url
      canonical_bucket = local.platform.canonical_bucket_name
      result_bucket    = local.platform.canonical_bucket_name
      result_prefix    = var.ingestion_result_prefix

      sqs_wait_time_seconds        = 20
      visibility_timeout_seconds   = var.sqs_visibility_timeout_seconds
      visibility_extension_seconds = var.sqs_visibility_extension_seconds
      visibility_heartbeat_seconds = var.sqs_visibility_heartbeat_seconds

      processing_registry_table          = module.ingestion_registry.table_name
      processing_claim_lease_seconds     = var.processing_claim_lease_seconds
      processing_claim_heartbeat_seconds = var.processing_claim_heartbeat_seconds
      processing_record_ttl_days         = var.processing_record_ttl_days

      ingestion_schema_version = var.ingestion_schema_version

      chunker_type    = var.chunker_type
      chunker_version = var.chunker_version
      chunk_size      = var.chunk_size
      chunk_overlap   = var.chunk_overlap

      index_schema_version                  = var.index_schema_version
      opensearch_deployment_type            = var.opensearch_deployment_type
      opensearch_endpoint                   = local.platform.opensearch_collection_endpoint
      opensearch_region                     = var.aws_region
      opensearch_index_prefix               = var.opensearch_index_prefix
      opensearch_refresh_after_index        = tostring(var.opensearch_refresh_after_index)
      opensearch_bulk_max_records           = tostring(var.opensearch_bulk_max_records)
      opensearch_bulk_max_bytes             = tostring(var.opensearch_bulk_max_bytes)
      opensearch_bulk_max_attempts          = tostring(var.opensearch_bulk_max_attempts)
      opensearch_visibility_timeout_seconds = tostring(var.opensearch_visibility_timeout_seconds)
      opensearch_visibility_poll_seconds    = tostring(var.opensearch_visibility_poll_seconds)

      cpu    = var.ecs_cpu
      memory = var.ecs_memory

      embedding_provider      = var.embedding_provider
      embedding_model_id      = var.embedding_model_id
      embedding_dimensions    = var.embedding_dimensions
      embedding_normalize     = tostring(var.embedding_normalize)
      embedding_model_options = jsonencode(var.embedding_model_options)

      huggingface_api_provider        = var.huggingface_api_provider
      huggingface_api_base_url        = var.huggingface_api_base_url
      huggingface_api_timeout_seconds = var.huggingface_api_timeout_seconds
      huggingface_api_max_attempts    = var.huggingface_api_max_attempts
      huggingface_api_token           = var.huggingface_api_token
    }
  )

  desired_count = var.ecs_min_capacity

  subnet_ids = local.platform.public_subnet_ids

  security_group_ids = [
    module.ingestion_security_group.security_group_id
  ]

  requires_compatibilities = [
    "FARGATE"
  ]

  network_mode            = "awsvpc"
  operating_system_family = "LINUX"
  cpu_architecture        = "X86_64"
  launch_type             = "FARGATE"

  enable_execute_command = true
  assign_public_ip       = true

  deployment_minimum_healthy_percent = 0
  deployment_maximum_percent         = 100
}
