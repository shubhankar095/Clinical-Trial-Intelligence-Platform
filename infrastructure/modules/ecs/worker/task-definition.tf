resource "aws_ecs_task_definition" "this" {
  family = var.task_family

  requires_compatibilities = var.requires_compatibilities

  cpu    = var.cpu
  memory = var.memory

  network_mode = var.network_mode

  execution_role_arn = var.execution_role_arn
  task_role_arn      = var.task_role_arn

  container_definitions = var.container_definitions_json

  runtime_platform {
    operating_system_family = var.operating_system_family
    cpu_architecture        = var.cpu_architecture
  }

  tags = var.tags
}