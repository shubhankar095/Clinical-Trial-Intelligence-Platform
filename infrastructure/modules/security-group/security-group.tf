resource "aws_security_group" "this" {
  name = var.security_group_name

  description = var.description

  vpc_id = var.vpc_id

  ingress = []

  egress {
    from_port = 0
    to_port   = 0
    protocol  = "-1"

    cidr_blocks = var.egress_ipv4_cidr_blocks
  }

  tags = merge(
    var.tags,
    {
      Name = var.security_group_name
    }
  )
}