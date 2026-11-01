output "vpc_id" {
  description = "ID of the shared VPC."
  value       = aws_vpc.this.id
}

output "vpc_arn" {
  description = "ARN of the shared VPC."
  value       = aws_vpc.this.arn
}

output "public_subnet_ids" {
  description = "Public subnet IDs in stable key order."
  value = [
    for key in sort(keys(aws_subnet.public)) :
    aws_subnet.public[key].id
  ]
}

output "public_route_table_id" {
  description = "ID of the public route table."
  value       = aws_route_table.public.id
}
