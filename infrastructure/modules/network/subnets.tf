resource "aws_subnet" "public" {
  for_each = var.public_subnets

  vpc_id = aws_vpc.this.id

  cidr_block        = each.value.cidr_block
  availability_zone = data.aws_availability_zones.available.names[each.value.availability_zone_index]

  map_public_ip_on_launch = var.map_public_ip_on_launch

  tags = merge(
    var.tags,
    {
      Name = each.value.name
    }
  )
}
