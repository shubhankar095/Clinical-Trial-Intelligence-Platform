# -----------------------------------------------------------------------------
# IAM permissions
# -----------------------------------------------------------------------------

module "extraction_permissions" {
  source = "../../../infrastructure/modules/iam/policy"

  policy_name = local.names.permissions_policy

  policy_json = templatefile(
    "${path.module}/templates/extraction-permissions-policy.json.tpl",
    {
      raw_bucket              = local.platform.raw_bucket_name
      canonical_bucket        = local.platform.canonical_bucket_name
      queue_arn               = module.extraction_queue.queue_arn
      processing_registry_arn = module.extraction_registry.table_arn
    }
  )
}

module "extraction_task_role" {
  source = "../../../infrastructure/modules/iam/role"

  role_name = local.names.task_role

  trust_policy_json = templatefile(
    "${path.module}/templates/extraction-trust-policy.json.tpl",
    {}
  )

  policy_arns = {
    task_permissions = module.extraction_permissions.policy_arn
  }
}

module "extraction_execution_role" {
  source = "../../../infrastructure/modules/iam/role"

  role_name = local.names.execution_role

  trust_policy_json = templatefile(
    "${path.module}/templates/extraction-trust-policy.json.tpl",
    {}
  )

  policy_arns = {
    ecs_task_execution = "arn:aws:iam::aws:policy/service-role/AmazonECSTaskExecutionRolePolicy"
  }
}

# -----------------------------------------------------------------------------
# Logging
# -----------------------------------------------------------------------------

module "extraction_logs" {
  source = "../../../infrastructure/modules/observability/logs"

  log_group_name    = local.names.log_group
  retention_in_days = var.log_retention_days
  name_tag          = local.names.log_group_name_tag
}

# -----------------------------------------------------------------------------
# ECS worker
# -----------------------------------------------------------------------------

module "extraction_worker" {
  source = "../../../infrastructure/modules/ecs/worker"

  task_family  = local.names.task_family
  service_name = local.names.ecs_service
  cluster_id   = local.platform.ecs_cluster_id

  cpu    = var.ecs_cpu
  memory = var.ecs_memory

  execution_role_arn = module.extraction_execution_role.role_arn
  task_role_arn      = module.extraction_task_role.role_arn

  container_definitions_json = templatefile(
    "${path.module}/templates/ecs-task-definition.json.tpl",
    {
      image_uri                          = "${module.extraction_repository.repository_url}:${var.image_tag}"
      log_group                          = module.extraction_logs.log_group_name
      region                             = var.aws_region
      environment                        = var.environment
      queue_url                          = module.extraction_queue.queue_url
      canonical_bucket                   = local.platform.canonical_bucket_name
      visibility_extension_seconds       = var.sqs_visibility_extension_seconds
      visibility_heartbeat_seconds       = var.sqs_visibility_heartbeat_seconds
      processing_schema_version          = var.processing_schema_version
      processing_registry_table          = module.extraction_registry.table_name
      processing_claim_lease_seconds     = var.processing_claim_lease_seconds
      processing_claim_heartbeat_seconds = var.processing_claim_heartbeat_seconds
      cpu                                = var.ecs_cpu
      memory                             = var.ecs_memory
    }
  )

  desired_count = var.ecs_min_capacity

  subnet_ids = local.platform.public_subnet_ids

  security_group_ids = [
    module.extraction_security_group.security_group_id
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
