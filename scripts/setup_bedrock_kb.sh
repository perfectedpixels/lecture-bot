#!/bin/bash

# Setup Bedrock Knowledge Base
# This script helps configure the Knowledge Base after infrastructure deployment

echo "=== Bedrock Knowledge Base Setup ==="
echo ""
echo "After deploying the CDK stack, follow these steps:"
echo ""
echo "1. Go to AWS Bedrock Console > Knowledge Bases"
echo "2. Click 'Create knowledge base'"
echo "3. Configure:"
echo "   - Name: LectureBot-KB"
echo "   - IAM Role: Use the BedrockRoleArn from stack outputs"
echo "   - Data source: S3"
echo "   - S3 URI: s3://<BucketName from outputs>/lectures/"
echo "   - Embeddings model: amazon.titan-embed-text-v1"
echo "   - Vector database: OpenSearch Serverless (or create new)"
echo ""
echo "4. After creation, sync the data source"
echo "5. Note the Knowledge Base ID for querying"
echo ""
echo "Stack Outputs:"
aws cloudformation describe-stacks --stack-name LectureBotStack --query "Stacks[0].Outputs" --output table
