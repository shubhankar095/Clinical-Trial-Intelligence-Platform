resource "aws_appautoscaling_target" "ecs" {
  max_capacity = var.max_capacity
  min_capacity = var.min_capacity

  resource_id = "service/${var.ecs_cluster_name}/${var.ecs_service_name}"

  scalable_dimension = "ecs:service:DesiredCount"
  service_namespace  = "ecs"
}