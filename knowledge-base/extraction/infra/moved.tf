moved {
  from = aws_vpc.main
  to   = module.foundation.aws_vpc.main
}

moved {
  from = aws_subnet.public_a
  to   = module.foundation.aws_subnet.public_a
}

moved {
  from = aws_subnet.public_b
  to   = module.foundation.aws_subnet.public_b
}

moved {
  from = aws_internet_gateway.main
  to   = module.foundation.aws_internet_gateway.main
}

moved {
  from = aws_route_table.public
  to   = module.foundation.aws_route_table.public
}

moved {
  from = aws_route_table_association.public_a
  to   = module.foundation.aws_route_table_association.public_a
}

moved {
  from = aws_route_table_association.public_b
  to   = module.foundation.aws_route_table_association.public_b
}

moved {
  from = aws_security_group.ecs
  to   = module.foundation.aws_security_group.ecs
}

moved {
  from = aws_s3_bucket.raw
  to   = module.foundation.aws_s3_bucket.raw
}

moved {
  from = aws_s3_bucket.canonical
  to   = module.foundation.aws_s3_bucket.canonical
}

moved {
  from = aws_s3_bucket_versioning.raw
  to   = module.foundation.aws_s3_bucket_versioning.raw
}

moved {
  from = aws_s3_bucket_versioning.canonical
  to   = module.foundation.aws_s3_bucket_versioning.canonical
}

moved {
  from = aws_s3_bucket_server_side_encryption_configuration.raw
  to   = module.foundation.aws_s3_bucket_server_side_encryption_configuration.raw
}

moved {
  from = aws_s3_bucket_server_side_encryption_configuration.canonical
  to   = module.foundation.aws_s3_bucket_server_side_encryption_configuration.canonical
}

moved {
  from = aws_s3_bucket_public_access_block.raw
  to   = module.foundation.aws_s3_bucket_public_access_block.raw
}

moved {
  from = aws_s3_bucket_public_access_block.canonical
  to   = module.foundation.aws_s3_bucket_public_access_block.canonical
}

moved {
  from = aws_sqs_queue_policy.s3_send_message
  to   = module.foundation.aws_sqs_queue_policy.s3_send_message
}

moved {
  from = aws_s3_bucket_notification.raw_uploads
  to   = module.foundation.aws_s3_bucket_notification.raw_uploads
}

moved {
  from = aws_s3_bucket_lifecycle_configuration.raw
  to   = module.foundation.aws_s3_bucket_lifecycle_configuration.raw
}

moved {
  from = aws_s3_bucket_lifecycle_configuration.canonical
  to   = module.foundation.aws_s3_bucket_lifecycle_configuration.canonical
}

moved {
  from = aws_sqs_queue.extraction_dlq
  to   = module.foundation.aws_sqs_queue.extraction_dlq
}

moved {
  from = aws_sqs_queue.extraction_queue
  to   = module.foundation.aws_sqs_queue.extraction_queue
}

moved {
  from = aws_dynamodb_table.processing_registry
  to   = module.foundation.aws_dynamodb_table.processing_registry
}

moved {
  from = aws_sns_topic.alerts
  to   = module.foundation.aws_sns_topic.alerts
}

moved {
  from = aws_sns_topic_subscription.email
  to   = module.foundation.aws_sns_topic_subscription.email
}

moved {
  from = aws_ecr_repository.extraction
  to   = module.worker.aws_ecr_repository.extraction
}

moved {
  from = aws_ecr_lifecycle_policy.extraction
  to   = module.worker.aws_ecr_lifecycle_policy.extraction
}

moved {
  from = aws_iam_role.ecs_task_role
  to   = module.worker.aws_iam_role.ecs_task_role
}

moved {
  from = aws_iam_role.ecs_execution_role
  to   = module.worker.aws_iam_role.ecs_execution_role
}

moved {
  from = aws_iam_policy.extraction
  to   = module.worker.aws_iam_policy.extraction
}

moved {
  from = aws_iam_role_policy_attachment.task
  to   = module.worker.aws_iam_role_policy_attachment.task
}

moved {
  from = aws_iam_role_policy_attachment.execution
  to   = module.worker.aws_iam_role_policy_attachment.execution
}

moved {
  from = aws_cloudwatch_log_group.extraction
  to   = module.worker.aws_cloudwatch_log_group.extraction
}

moved {
  from = aws_ecs_cluster.extraction
  to   = module.worker.aws_ecs_cluster.extraction
}

moved {
  from = aws_ecs_task_definition.extraction
  to   = module.worker.aws_ecs_task_definition.extraction
}

moved {
  from = aws_ecs_service.extraction
  to   = module.worker.aws_ecs_service.extraction
}

moved {
  from = aws_appautoscaling_target.ecs
  to   = module.autoscaling.aws_appautoscaling_target.ecs
}

moved {
  from = aws_appautoscaling_policy.backlog_per_task
  to   = module.autoscaling.aws_appautoscaling_policy.backlog_per_task
}

moved {
  from = aws_appautoscaling_policy.queue_drained_to_one
  to   = module.autoscaling.aws_appautoscaling_policy.queue_drained_to_one
}

moved {
  from = aws_appautoscaling_policy.idle_scale_to_zero
  to   = module.autoscaling.aws_appautoscaling_policy.idle_scale_to_zero
}

moved {
  from = aws_appautoscaling_policy.bootstrap_scale_out
  to   = module.autoscaling.aws_appautoscaling_policy.bootstrap_scale_out
}

moved {
  from = aws_cloudwatch_metric_alarm.queue_drained_to_one
  to   = module.autoscaling.aws_cloudwatch_metric_alarm.queue_drained_to_one
}

moved {
  from = aws_cloudwatch_metric_alarm.queue_depth_empty
  to   = module.autoscaling.aws_cloudwatch_metric_alarm.queue_depth_empty
}

moved {
  from = aws_cloudwatch_metric_alarm.bootstrap_queue_not_empty
  to   = module.autoscaling.aws_cloudwatch_metric_alarm.bootstrap_queue_not_empty
}

moved {
  from = aws_cloudwatch_metric_alarm.dlq_messages
  to   = module.observability.aws_cloudwatch_metric_alarm.dlq_messages
}

moved {
  from = aws_cloudwatch_metric_alarm.oldest_message_age
  to   = module.observability.aws_cloudwatch_metric_alarm.oldest_message_age
}

moved {
  from = aws_cloudwatch_log_metric_filter.processing_failures
  to   = module.observability.aws_cloudwatch_log_metric_filter.processing_failures
}

moved {
  from = aws_cloudwatch_metric_alarm.processing_failures
  to   = module.observability.aws_cloudwatch_metric_alarm.processing_failures
}

moved {
  from = aws_cloudwatch_log_metric_filter.processing_successes
  to   = module.observability.aws_cloudwatch_log_metric_filter.processing_successes
}

moved {
  from = aws_cloudwatch_log_metric_filter.processing_duration
  to   = module.observability.aws_cloudwatch_log_metric_filter.processing_duration
}

moved {
  from = aws_cloudwatch_dashboard.extraction
  to   = module.observability.aws_cloudwatch_dashboard.extraction
}
