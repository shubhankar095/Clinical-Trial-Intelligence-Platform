{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowS3SendMessage",
      "Effect": "Allow",
      "Principal": {
        "Service": "s3.amazonaws.com"
      },
      "Action": "sqs:SendMessage",
      "Resource": "${queue_arn}",
      "Condition": {
        "ArnEquals": {
          "aws:SourceArn": "${bucket_arn}"
        },
        "StringEquals": {
          "aws:SourceAccount": "${source_account_id}"
        }
      }
    }
  ]
}
