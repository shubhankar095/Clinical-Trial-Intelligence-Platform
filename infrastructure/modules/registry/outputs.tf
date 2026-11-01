output "table_id" {
  description = "ID of the DynamoDB processing-registry table."
  value       = aws_dynamodb_table.this.id
}

output "table_name" {
  description = "Name of the DynamoDB processing-registry table."
  value       = aws_dynamodb_table.this.name
}

output "table_arn" {
  description = "ARN of the DynamoDB processing-registry table."
  value       = aws_dynamodb_table.this.arn
}