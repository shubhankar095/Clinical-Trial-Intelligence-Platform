# -----------------------------------------------------------------------------
# Autoscaling
# -----------------------------------------------------------------------------

module "extraction_autoscaling" {
  source = "../../../infrastructure/modules/autoscaling/ecs-sqs/backlog-per-task"

  names        = local.autoscaling_names
  labels       = local.autoscaling_labels
  descriptions = local.autoscaling_descriptions

  sqs_queue_name   = module.extraction_queue.queue_name
  ecs_cluster_name = local.platform.ecs_cluster_name
  ecs_service_name = module.extraction_worker.service_name

  min_capacity = var.ecs_min_capacity
  max_capacity = var.ecs_max_capacity

  backlog_per_task_target = var.backlog_per_task_target

  scale_out_cooldown_seconds = var.ecs_scale_out_cooldown_seconds
  scale_in_cooldown_seconds  = var.ecs_scale_in_cooldown_seconds

  queue_drained_evaluation_periods = var.queue_drained_evaluation_periods
  queue_drained_cooldown_seconds   = var.queue_drained_scale_in_cooldown_seconds

  scale_to_zero_evaluation_periods    = var.scale_to_zero_evaluation_periods
  idle_scale_to_zero_cooldown_seconds = var.idle_scale_to_zero_cooldown_seconds
}

# -----------------------------------------------------------------------------
# Monitoring
# -----------------------------------------------------------------------------

module "extraction_monitoring" {
  source = "../../../infrastructure/modules/observability/monitoring"

  names            = local.monitoring_names
  metric_namespace = local.metric_namespace

  display = {
    service_name      = var.service_name
    environment_name  = var.environment
    dashboard_heading = "# Clinical Knowledge Base: Extraction"
  }

  alarm_descriptions = local.monitoring_alarm_descriptions

  aws_region = var.aws_region

  queue_name       = module.extraction_queue.queue_name
  dlq_name         = module.extraction_queue.dlq_name
  ecs_cluster_name = local.platform.ecs_cluster_name
  ecs_service_name = module.extraction_worker.service_name
  log_group_name   = module.extraction_logs.log_group_name
  alert_topic_arn  = module.extraction_notifications.topic_arn

  bootstrap_alarm_arn     = module.extraction_autoscaling.bootstrap_alarm_arn
  queue_drained_alarm_arn = module.extraction_autoscaling.queue_drained_alarm_arn
  queue_empty_alarm_arn   = module.extraction_autoscaling.queue_empty_alarm_arn

  backlog_per_task_target      = var.backlog_per_task_target
  oldest_message_alarm_seconds = var.oldest_message_alarm_seconds

  processing_failure_filter_pattern  = "\"Message processing failed\""
  processing_success_filter_pattern  = "{ $.event = \"document_processed\" && $.processing_status = \"SUCCESS\" }"
  processing_duration_filter_pattern = "{ $.event = \"document_processed\" && $.duration_seconds = * }"
}
