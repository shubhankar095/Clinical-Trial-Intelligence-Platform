output "ecs_cluster_name" { value = aws_ecs_cluster.extraction.name }
output "ecs_service_name" { value = aws_ecs_service.extraction.name }
output "ecr_repository_url" { value = aws_ecr_repository.extraction.repository_url }
output "image_uri" { value = "${aws_ecr_repository.extraction.repository_url}:${var.image_tag}" }
output "cloudwatch_log_group_name" { value = aws_cloudwatch_log_group.extraction.name }
