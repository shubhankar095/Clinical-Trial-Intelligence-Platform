
resource "aws_sns_topic" "this" {
  name = var.topic_name

  tags = merge(
    var.tags,
    {
      Name = var.topic_name
    }
  )
}
