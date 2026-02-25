#!/bin/bash

# Download affinity map from S3 for use in Streamlit app
# Usage: ./download_affinity_map.sh [output_path]

OUTPUT_PATH=${1:-"processed_lectures/affinity_map.json"}

# Get bucket name
BUCKET_NAME=$(aws cloudformation describe-stacks \
  --stack-name LectureBotStack \
  --query "Stacks[0].Outputs[?OutputKey=='BucketName'].OutputValue" \
  --output text)

if [ -z "$BUCKET_NAME" ]; then
    echo "Error: Could not find bucket name. Make sure LectureBotStack is deployed."
    exit 1
fi

echo "Downloading affinity map from S3..."
aws s3 cp "s3://${BUCKET_NAME}/metadata/affinity_map.json" "$OUTPUT_PATH"

if [ $? -eq 0 ]; then
    echo "✓ Downloaded to $OUTPUT_PATH"
    echo ""
    echo "Upload this file in the Streamlit app sidebar to enable concept-aware responses."
else
    echo "✗ Download failed. Make sure the affinity map has been uploaded to S3."
fi
