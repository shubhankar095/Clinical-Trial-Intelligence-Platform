{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "ReadCanonicalDocuments",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:GetObjectVersion"
      ],
      "Resource": [
        "arn:aws:s3:::${canonical_bucket}/canonical-documents/*"
      ]
    },
    {
      "Sid": "ReadAndWriteIngestionResults",
      "Effect": "Allow",
      "Action": [
        "s3:GetObject",
        "s3:GetObjectVersion",
        "s3:PutObject"
      ],
      "Resource": [
        "arn:aws:s3:::${result_bucket}/${result_prefix}/*"
      ]
    },
    {
      "Sid": "ConsumeIngestionMessages",
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
      "Sid": "ManageIngestionClaims",
      "Effect": "Allow",
      "Action": [
        "dynamodb:GetItem",
        "dynamodb:UpdateItem"
      ],
      "Resource": [
        "${processing_registry_arn}"
      ]
    },
%{ if opensearch_deployment_type == "serverless" ~}
    {
      "Sid": "AccessOpenSearchServerless",
      "Effect": "Allow",
      "Action": [
        "aoss:APIAccessAll"
      ],
      "Resource": [
        "${opensearch_resource_arn}"
      ]
    },
%{ else ~}
    {
      "Sid": "AccessOpenSearchDomain",
      "Effect": "Allow",
      "Action": [
        "es:ESHttpGet",
        "es:ESHttpPost",
        "es:ESHttpPut",
        "es:ESHttpDelete"
      ],
      "Resource": [
        "${opensearch_resource_arn}/*"
      ]
    },
%{ endif ~}
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
    }    
  ]
}