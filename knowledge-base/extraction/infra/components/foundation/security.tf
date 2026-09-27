resource "aws_security_group" "ecs" {

  name = "${local.project_prefix}-ecs-sg-${var.environment}"

  description = "Security group for extraction workers"

  vpc_id = aws_vpc.main.id

  ingress = []

  egress {
    from_port = 0
    to_port   = 0
    protocol  = "-1"
    cidr_blocks = [
      "0.0.0.0/0"
    ]
  }

  tags = merge(
    local.common_tags,
    {
      Name = "${local.project_prefix}-ecs-sg-${var.environment}"
    }
  )
}
