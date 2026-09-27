output "bootstrap_alarm_arn" { value = aws_cloudwatch_metric_alarm.bootstrap_queue_not_empty.arn }
output "queue_drained_alarm_arn" { value = aws_cloudwatch_metric_alarm.queue_drained_to_one.arn }
output "queue_empty_alarm_arn" { value = aws_cloudwatch_metric_alarm.queue_depth_empty.arn }
