locals {
  standard_tags = {
    Project     = var.project_name
    Environment = var.environment
    ManagedBy   = "Terraform"
    Service     = var.service_name
    Owner       = var.owner
  }

  names = {
    vpc                          = "${var.project_name}-vpc-${var.environment}"
    internet_gateway             = "${var.project_name}-igw-${var.environment}"
    public_route_table           = "${var.project_name}-public-${var.environment}"
    public_subnet_a              = "${var.project_name}-public-a-${var.environment}"
    public_subnet_b              = "${var.project_name}-public-b-${var.environment}"
    ecs_cluster                  = "${var.project_name}-cluster-${var.environment}"
    opensearch_collection        = "${var.project_name}-${var.environment}"
    opensearch_encryption_policy = "${var.project_name}-os-encryption-${var.environment}"
    opensearch_network_policy    = "${var.project_name}-os-network-${var.environment}"
    opensearch_collection_group  = "${var.project_name}-os-group-${var.environment}"
  }
}
