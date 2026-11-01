resource "aws_ecs_service" "this" {
  name = var.service_name

  cluster         = var.cluster_id
  task_definition = aws_ecs_task_definition.this.arn

  desired_count = var.desired_count

  deployment_minimum_healthy_percent = (
    var.deployment_minimum_healthy_percent
  )

  deployment_maximum_percent = (
    var.deployment_maximum_percent
  )

  launch_type = var.launch_type

  enable_execute_command = var.enable_execute_command

  network_configuration {
    subnets = var.subnet_ids

    security_groups = var.security_group_ids

    assign_public_ip = var.assign_public_ip
  }

  lifecycle {
    ignore_changes = [
      desired_count
    ]
  }

  tags = merge(
    var.tags,
    {
      Name = var.service_name
    }
  )
}