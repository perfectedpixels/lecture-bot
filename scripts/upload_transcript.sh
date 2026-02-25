#!/bin/bash

# Upload lecture transcript to S3
# Usage: ./upload_transcript.sh <file_path> <lecture_name>

if [ $# -lt 2 ]; then
    echo "Usage: $0 <file_path> <lecture_name>"
    echo "Example: $0 lecture1.txt 'Introduction to AI'"
    exit 1
fi

FILE_PATH=$1
LECTURE_NAME=$2
BUCKET_NAME=$(aws cloudformation describe-stacks --stack-name LectureBotStack --query "Stacks[0].Outputs[?OutputKey=='BucketName'].OutputValue" --output text)

if [ -z "$BUCKET_NAME" ]; then
    echo "Error: Could not find bucket name. Make sure the stack is deployed."
    exit 1
fi

# Generate S3 key with timestamp
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
S3_KEY="lectures/${TIMESTAMP}_${LECTURE_NAME}.txt"

echo "Uploading to s3://${BUCKET_NAME}/${S3_KEY}"
aws s3 cp "$FILE_PATH" "s3://${BUCKET_NAME}/${S3_KEY}" \
    --metadata "lecture_name=${LECTURE_NAME},upload_date=$(date -u +%Y-%m-%dT%H:%M:%SZ)"

echo "Upload complete!"
