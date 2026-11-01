output "scalable_target_resource_id" {
  description = "Application Auto Scaling resource ID."
  value       = aws_appautoscaling_target.ecs.resource_id
}

output "backlog_policy_arn" {
  description = "ARN of the backlog-per-task target-tracking policy."
  value       = aws_appautoscaling_policy.backlog_per_task.arn
}

output "bootstrap_policy_arn" {
  description = "ARN of the bootstrap scale-out policy."
  value       = aws_appautoscaling_policy.bootstrap_scale_out.arn
}

output "queue_drained_policy_arn" {
  description = "ARN of the queue-drained scale-to-one policy."
  value       = aws_appautoscaling_policy.queue_drained_to_one.arn
}

output "idle_scale_to_zero_policy_arn" {
  description = "ARN of the idle scale-to-zero policy."
  value       = aws_appautoscaling_policy.idle_scale_to_zero.arn
}

output "bootstrap_alarm_arn" {
  description = "ARN of the bootstrap queue-not-empty alarm."
  value       = aws_cloudwatch_metric_alarm.bootstrap_queue_not_empty.arn
}

output "queue_drained_alarm_arn" {
  description = "ARN of the queue-drained-to-one alarm."
  value       = aws_cloudwatch_metric_alarm.queue_drained_to_one.arn
}

output "queue_empty_alarm_arn" {
  description = "ARN of the sustained-idle queue-empty alarm."
  value       = aws_cloudwatch_metric_alarm.queue_depth_empty.arn
}