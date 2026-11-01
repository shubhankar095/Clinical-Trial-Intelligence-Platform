locals {
  service_slug   = lower(var.service_name)
  service_prefix = "${var.project_name}-${local.service_slug}"

  standard_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "Terraform"
    Service     = var.service_name
    Owner       = var.owner
  }

  platform = {
    vpc_id                = data.terraform_remote_state.platform.outputs.vpc_id
    public_subnet_ids     = data.terraform_remote_state.platform.outputs.public_subnet_ids
    raw_bucket_name       = data.terraform_remote_state.platform.outputs.raw_bucket_name
    raw_bucket_arn        = data.terraform_remote_state.platform.outputs.raw_bucket_arn
    canonical_bucket_name = data.terraform_remote_state.platform.outputs.canonical_bucket_name
    canonical_bucket_arn  = data.terraform_remote_state.platform.outputs.canonical_bucket_arn
    ecs_cluster_id        = data.terraform_remote_state.platform.outputs.ecs_cluster_id
    ecs_cluster_name      = data.terraform_remote_state.platform.outputs.ecs_cluster_name
  }

  names = {
    queue               = "${local.service_prefix}-${var.environment}"
    dlq                 = "${local.service_prefix}-dlq-${var.environment}"
    processing_registry = "${local.service_prefix}-processing-${var.environment}"
    repository          = "${local.service_prefix}-${var.environment}"
    security_group      = "${local.service_prefix}-ecs-sg-${var.environment}"
    alert_topic         = "${local.service_prefix}-alerts-${var.environment}"
    task_role           = "${local.service_prefix}-task-role-${var.environment}"
    execution_role      = "${local.service_prefix}-execution-role-${var.environment}"
    permissions_policy  = "${local.service_prefix}-permissions-${var.environment}"
    task_family         = "${local.service_prefix}-task-${var.environment}"
    ecs_service         = "${local.service_prefix}-service-${var.environment}"
    log_group           = "/ecs/${local.service_prefix}-${var.environment}"
    log_group_name_tag  = "${local.service_prefix}-${var.environment}"
  }

  autoscaling_names = {
    backlog_policy       = "${local.service_prefix}-backlog-per-task-${var.environment}"
    bootstrap_policy     = "${local.service_prefix}-bootstrap-scale-out-${var.environment}"
    bootstrap_alarm      = "${local.service_prefix}-bootstrap-queue-not-empty-${var.environment}"
    queue_drained_policy = "${local.service_prefix}-queue-drained-to-one-${var.environment}"
    queue_drained_alarm  = "${local.service_prefix}-queue-drained-to-one-${var.environment}"
    idle_policy          = "${local.service_prefix}-idle-scale-to-zero-${var.environment}"
    queue_empty_alarm    = "${local.service_prefix}-queue-depth-empty-${var.environment}"
  }

  autoscaling_labels = {
    visible_messages         = "Visible ${local.service_slug} messages"
    running_tasks            = "Running ${local.service_slug} tasks"
    backlog_per_task         = "${var.service_name} backlog per task"
    bootstrap_expression     = "Visible messages requiring bootstrap"
    queue_drained_expression = "Outstanding work while excess workers are running"
    idle_expression          = "Outstanding work while final worker remains"
  }

  autoscaling_descriptions = {
    bootstrap_alarm     = "Start exactly one ${local.service_slug} worker when visible messages exist and no ECS worker is running."
    queue_drained_alarm = "Reduce excess ${local.service_slug} workers directly to one after visible, in-flight, and delayed messages remain zero for the configured drain window."
    idle_alarm          = "Set ${local.service_slug} capacity to zero after visible, in-flight, and delayed messages remain zero for the configured idle window."
  }

  monitoring_names = {
    processing_failures_filter  = "${local.service_prefix}-processing-failures-${var.environment}"
    processing_successes_filter = "${local.service_prefix}-processing-successes-${var.environment}"
    processing_duration_filter  = "${local.service_prefix}-processing-duration-${var.environment}"
    dlq_alarm                   = "${local.service_prefix}-dlq-messages-${var.environment}"
    oldest_message_alarm        = "${local.service_prefix}-oldest-message-${var.environment}"
    processing_failures_alarm   = "${local.service_prefix}-processing-failures-${var.environment}"
    dashboard                   = "${local.service_prefix}-${var.environment}"
  }

  monitoring_alarm_descriptions = {
    dlq                 = "${var.service_name} messages have reached the dead-letter queue."
    oldest_message      = "${var.service_name} messages have remained unprocessed beyond the configured threshold."
    processing_failures = "The ${local.service_slug} worker logged one or more message-processing failures."
  }

  metric_namespace = "${var.project_name}/${var.service_name}/${var.environment}"
}
