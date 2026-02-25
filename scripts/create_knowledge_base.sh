#!/bin/bash

# Create Bedrock Knowledge Base with OpenSearch Serverless
# This script automates the KB creation process

set -e

BUCKET_NAME="lecture-transcripts-427791004700"
ROLE_ARN="arn:aws:iam::427791004700:role/LectureBotStack-BedrockKBRole10C55766-rzguFD8wlHg5"
REGION="us-east-1"
COLLECTION_NAME="lecture-bot-kb"
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

echo "Creating OpenSearch Serverless security policies..."

# Create encryption policy
aws opensearchserverless create-security-policy \
  --name "${COLLECTION_NAME}-encryption" \
  --type encryption \
  --policy "{\"Rules\":[{\"ResourceType\":\"collection\",\"Resource\":[\"collection/${COLLECTION_NAME}\"]}],\"AWSOwnedKey\":true}" \
  --region "$REGION" || echo "Encryption policy may already exist"

# Create network policy
aws opensearchserverless create-security-policy \
  --name "${COLLECTION_NAME}-network" \
  --type network \
  --policy "[{\"Rules\":[{\"ResourceType\":\"collection\",\"Resource\":[\"collection/${COLLECTION_NAME}\"]},{\"ResourceType\":\"dashboard\",\"Resource\":[\"collection/${COLLECTION_NAME}\"]}],\"AllowFromPublic\":true}]" \
  --region "$REGION" || echo "Network policy may already exist"

echo "Creating OpenSearch Serverless collection..."

# Create collection
COLLECTION_ARN=$(aws opensearchserverless create-collection \
  --name "$COLLECTION_NAME" \
  --type VECTORSEARCH \
  --region "$REGION" \
  --query 'createCollectionDetail.arn' \
  --output text)

echo "Collection ARN: $COLLECTION_ARN"
echo "Waiting for collection to become active (this takes ~2 minutes)..."

# Wait for collection to be active
for i in {1..24}; do
  STATUS=$(aws opensearchserverless batch-get-collection \
    --names "$COLLECTION_NAME" \
    --region "$REGION" \
    --query 'collectionDetails[0].status' \
    --output text)
  
  if [ "$STATUS" == "ACTIVE" ]; then
    echo "Collection is active!"
    break
  fi
  echo "Status: $STATUS - waiting..."
  sleep 10
done

# Get collection endpoint
COLLECTION_ENDPOINT=$(aws opensearchserverless batch-get-collection \
  --names "$COLLECTION_NAME" \
  --region "$REGION" \
  --query 'collectionDetails[0].collectionEndpoint' \
  --output text)

echo "Collection Endpoint: $COLLECTION_ENDPOINT"

# Create data access policy for Bedrock role
echo "Creating data access policy..."
aws opensearchserverless create-access-policy \
  --name "${COLLECTION_NAME}-access" \
  --type data \
  --policy "[{\"Rules\":[{\"Resource\":[\"collection/${COLLECTION_NAME}\"],\"Permission\":[\"aoss:CreateCollectionItems\",\"aoss:UpdateCollectionItems\",\"aoss:DescribeCollectionItems\"],\"ResourceType\":\"collection\"},{\"Resource\":[\"index/${COLLECTION_NAME}/*\"],\"Permission\":[\"aoss:CreateIndex\",\"aoss:UpdateIndex\",\"aoss:DescribeIndex\",\"aoss:ReadDocument\",\"aoss:WriteDocument\"],\"ResourceType\":\"index\"}],\"Principal\":[\"${ROLE_ARN}\",\"arn:aws:iam::${ACCOUNT_ID}:role/Admin\"]}]" \
  --region "$REGION" || echo "Access policy may already exist"

# Create Knowledge Base
echo "Creating Bedrock Knowledge Base..."

KB_ID=$(aws bedrock-agent create-knowledge-base \
  --name "LectureBot-KB" \
  --description "Knowledge base for lecture transcripts" \
  --role-arn "$ROLE_ARN" \
  --knowledge-base-configuration "type=VECTOR,vectorKnowledgeBaseConfiguration={embeddingModelArn=arn:aws:bedrock:${REGION}::foundation-model/amazon.titan-embed-text-v2:0}" \
  --storage-configuration "type=OPENSEARCH_SERVERLESS,opensearchServerlessConfiguration={collectionArn=${COLLECTION_ARN},vectorIndexName=lecture-index,fieldMapping={vectorField=vector,textField=text,metadataField=metadata}}" \
  --region "$REGION" \
  --query 'knowledgeBase.knowledgeBaseId' \
  --output text)

echo "Knowledge Base ID: $KB_ID"

# Create Data Source
echo "Creating data source..."

DS_ID=$(aws bedrock-agent create-data-source \
  --knowledge-base-id "$KB_ID" \
  --name "S3-Lectures" \
  --data-source-configuration "type=S3,s3Configuration={bucketArn=arn:aws:s3:::${BUCKET_NAME},inclusionPrefixes=[lectures/]}" \
  --region "$REGION" \
  --query 'dataSource.dataSourceId' \
  --output text)

echo "Data Source ID: $DS_ID"

# Start ingestion
echo "Starting data ingestion..."

aws bedrock-agent start-ingestion-job \
  --knowledge-base-id "$KB_ID" \
  --data-source-id "$DS_ID" \
  --region "$REGION"

echo ""
echo "✅ Setup Complete!"
echo ""
echo "Knowledge Base ID: $KB_ID"
echo "Data Source ID: $DS_ID"
echo ""
echo "Copy the Knowledge Base ID above and paste it into the Streamlit app!"
echo ""
echo "Note: Ingestion may take 1-2 minutes. Check status with:"
echo "aws bedrock-agent list-ingestion-jobs --knowledge-base-id $KB_ID --data-source-id $DS_ID --region $REGION"
