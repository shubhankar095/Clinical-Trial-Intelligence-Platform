{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ReadRawDocuments",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:GetObjectVersion"
      ],
      "Resource": [
        "arn:aws:s3:::${raw_bucket}/documents/*"
      ]
    },
    {
      "Sid": "ListCanonicalDocuments",
      "Effect": "Allow",
      "Action": [
        "s3:ListBucket"
      ],
      "Resource": [
        "arn:aws:s3:::${canonical_bucket}"
      ],
      "Condition": {
        "StringLike": {
          "s3:prefix": [
            "canonical-documents/*"
          ]
        }
      }
    },
    {
      "Sid": "ManageCanonicalDocuments",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:PutObject",
        "s3:DeleteObject"
      ],
      "Resource": [
        "arn:aws:s3:::${canonical_bucket}/canonical-documents/*"
      ]
    },
    {
      "Sid": "ExtractTextWithTextract",
      "Effect": "Allow",
      "Action": [
        "textract:DetectDocumentText"
      ],
      "Resource": "*"
    },
    {
      "Sid": "ConsumeExtractionMessages",
      "Effect": "Allow",
      "Action": [
        "sqs:ReceiveMessage",
        "sqs:DeleteMessage",
        "sqs:ChangeMessageVisibility",
        "sqs:GetQueueAttributes"
      ],
      "Resource": [
        "${queue_arn}"
      ]
    },
    {
      "Sid": "ExecuteCommandsInTask",
      "Effect": "Allow",
      "Action": [
        "ssmmessages:CreateControlChannel",
        "ssmmessages:CreateDataChannel",
        "ssmmessages:OpenControlChannel",
        "ssmmessages:OpenDataChannel"
      ],
      "Resource": "*"
    },
    {
      "Sid": "ManageProcessingClaims",
      "Effect": "Allow",
      "Action": [
        "dynamodb:GetItem",
        "dynamodb:PutItem",
        "dynamodb:UpdateItem",
        "dynamodb:DeleteItem"
      ],
      "Resource": [
        "${processing_registry_arn}"
      ]
    }
  ]
}
