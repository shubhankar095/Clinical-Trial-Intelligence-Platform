resource "aws_appautoscaling_target" "ecs" {
  max_capacity = var.ecs_max_capacity
  min_capacity = var.ecs_min_capacity

  resource_id = "service/${var.ecs_cluster_name}/${var.ecs_service_name}"

  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}
