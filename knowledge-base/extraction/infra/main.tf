# -----------------------------------------------------------------------------
# Messaging
# -----------------------------------------------------------------------------

module "extraction_queue" {
  source = "../../../infrastructure/modules/queue"

  queue_name = local.names.queue
  dlq_name   = local.names.dlq

  visibility_timeout_seconds    = var.sqs_visibility_timeout_seconds
  message_retention_seconds     = 604800
  receive_wait_time_seconds     = 20
  dlq_message_retention_seconds = 1209600
  max_receive_count             = var.sqs_max_receive_count
}

# -----------------------------------------------------------------------------
# Processing registry
# -----------------------------------------------------------------------------

module "extraction_registry" {
  source = "../../../infrastructure/modules/registry"

  table_name         = local.names.processing_registry
  partition_key      = "document_id"
  ttl_attribute_name = "ttl"
}

# -----------------------------------------------------------------------------
# Container repository
# -----------------------------------------------------------------------------

module "extraction_repository" {
  source = "../../../infrastructure/modules/repository"

  repository_name = local.names.repository
  force_delete    = var.environment == "dev"

  image_tag_mutability = var.environment == "dev" ? "MUTABLE" : "IMMUTABLE"
  scan_on_push         = true

  untagged_image_retention_days = 14
}

# -----------------------------------------------------------------------------
# Network security
# -----------------------------------------------------------------------------

module "extraction_security_group" {
  source = "../../../infrastructure/modules/security-group"

  security_group_name = local.names.security_group
  description         = "Security group for extraction workers"
  vpc_id              = local.platform.vpc_id

  egress_ipv4_cidr_blocks = [
    "0.0.0.0/0"
  ]
}

# -----------------------------------------------------------------------------
# Notifications
# -----------------------------------------------------------------------------

module "extraction_notifications" {
  source = "../../../infrastructure/modules/notifications"

  topic_name     = local.names.alert_topic
  email_endpoint = var.alert_email
}
