variable "vpc_name" {
  description = "Name assigned to the VPC."
  type        = string
}

variable "internet_gateway_name" {
  description = "Name assigned to the internet gateway."
  type        = string
}

variable "public_route_table_name" {
  description = "Name assigned to the public route table."
  type        = string
}

variable "vpc_cidr" {
  description = "CIDR block assigned to the VPC."
  type        = string
}

variable "public_subnets" {
  description = "Public subnet definitions keyed by a stable logical name."
  type = map(object({
    name                    = string
    cidr_block              = string
    availability_zone_index = number
  }))

  validation {
    condition     = length(var.public_subnets) >= 2
    error_message = "At least two public subnets are required."
  }
}

variable "enable_dns_support" {
  description = "Whether DNS resolution is enabled for the VPC."
  type        = bool
  default     = true
}

variable "enable_dns_hostnames" {
  description = "Whether DNS hostnames are enabled for the VPC."
  type        = bool
  default     = true
}

variable "map_public_ip_on_launch" {
  description = "Whether resources launched in public subnets receive public IP addresses."
  type        = bool
  default     = true
}

variable "tags" {
  description = "Tags applied to supported network resources."
  type        = map(string)
  default     = {}
}
