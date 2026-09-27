#!/bin/bash

echo "Configuring AWS credentials..."

mkdir -p ~/.aws

cp /workspaces/Clinical-Trial-Intelligence-Platform/.credentials \
   ~/.aws/credentials

cat > ~/.aws/config <<EOF
[default]
region = ap-south-1
output = json
EOF

echo ""
echo "Testing AWS connection..."
aws sts get-caller-identity

echo ""
echo "Testing boto3 credentials..."