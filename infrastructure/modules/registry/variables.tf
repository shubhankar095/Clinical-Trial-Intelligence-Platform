variable "table_name" {
  description = "Name assigned to the DynamoDB processing-registry table."
  type        = string

  validation {
    condition     = length(trimspace(var.table_name)) > 0
    error_message = "table_name must not be empty."
  }
}

variable "partition_key" {
  description = "String partition key used by the processing-registry table."
  type        = string
  default     = "document_id"

  validation {
    condition     = length(trimspace(var.partition_key)) > 0
    error_message = "partition_key must not be empty."
  }
}

variable "ttl_attribute_name" {
  description = "Attribute containing the DynamoDB TTL timestamp."
  type        = string
  default     = "ttl"

  validation {
    condition     = length(trimspace(var.ttl_attribute_name)) > 0
    error_message = "ttl_attribute_name must not be empty."
  }
}

variable "tags" {
  description = "Tags applied to the DynamoDB table."
  type        = map(string)
  default     = {}
}