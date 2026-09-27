resource "aws_ecs_cluster" "extraction" {
  name = "${local.project_prefix}-cluster-${var.environment}"

  setting {
    name  = "containerInsights"
    value = "enabled"
  }

  tags = merge(
    local.common_tags,
    {
      Name = "${local.project_prefix}-cluster-${var.environment}"
    }
  )
}


resource "aws_ecs_task_definition" "extraction" {
  family                   = "${local.project_prefix}-task-${var.environment}"
  requires_compatibilities = ["FARGATE"]

  cpu    = var.ecs_cpu
  memory = var.ecs_memory

  network_mode = "awsvpc"

  execution_role_arn = aws_iam_role.ecs_execution_role.arn
  task_role_arn      = aws_iam_role.ecs_task_role.arn

  container_definitions = templatefile(
    "${path.module}/templates/ecs-task-definition.json.tpl",
    {
      image_uri                          = "${aws_ecr_repository.extraction.repository_url}:${var.image_tag}"
      log_group                          = aws_cloudwatch_log_group.extraction.name
      region                             = var.aws_region
      environment                        = var.environment
      queue_url                          = var.extraction_queue_url
      canonical_bucket                   = var.canonical_bucket_name
      visibility_extension_seconds       = var.sqs_visibility_extension_seconds
      visibility_heartbeat_seconds       = var.sqs_visibility_heartbeat_seconds
      processing_schema_version          = var.processing_schema_version
      processing_registry_table          = var.processing_registry_name
      processing_claim_lease_seconds     = var.processing_claim_lease_seconds
      processing_claim_heartbeat_seconds = var.processing_claim_heartbeat_seconds
      cpu                                = var.ecs_cpu
      memory                             = var.ecs_memory
    }
  )

  runtime_platform {
    operating_system_family = "LINUX"
    cpu_architecture        = "X86_64"
  }
}


resource "aws_ecs_service" "extraction" {
  name            = "${local.project_prefix}-service-${var.environment}"
  cluster         = aws_ecs_cluster.extraction.id
  task_definition = aws_ecs_task_definition.extraction.arn

  desired_count                      = var.ecs_min_capacity
  deployment_minimum_healthy_percent = 0
  deployment_maximum_percent         = 100

  launch_type            = "FARGATE"
  enable_execute_command = true

  network_configuration {

    subnets = var.subnet_ids

    security_groups = [
      var.security_group_id
    ]

    assign_public_ip = true
  }
  lifecycle {
    ignore_changes = [
      desired_count
    ]
  }
  tags = merge(
    local.common_tags,
    {
      Name = "${local.project_prefix}-service-${var.environment}"
    }
  )
}
