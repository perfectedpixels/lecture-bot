#!/bin/bash

# Upload processed lecture segments to S3 for Bedrock Knowledge Base
# Usage: ./upload_processed_to_s3.sh <processed_dir>

if [ $# -lt 1 ]; then
    echo "Usage: $0 <processed_dir>"
    echo "Example: $0 processed_lectures/"
    exit 1
fi

PROCESSED_DIR=$1

# Get bucket name from CloudFormation
BUCKET_NAME=$(aws cloudformation describe-stacks \
  --stack-name LectureBotStack \
  --query "Stacks[0].Outputs[?OutputKey=='BucketName'].OutputValue" \
  --output text)

if [ -z "$BUCKET_NAME" ]; then
    echo "Error: Could not find bucket name. Make sure LectureBotStack is deployed."
    exit 1
fi

echo "=== Uploading Processed Lectures to S3 ==="
echo "Bucket: $BUCKET_NAME"
echo "Source: $PROCESSED_DIR"
echo ""

# Check if jq is installed
if ! command -v jq &> /dev/null; then
    echo "Error: jq is required but not installed."
    echo "Install with: brew install jq"
    exit 1
fi

# Create temp directory for text files
TEMP_DIR=$(mktemp -d)
echo "Creating temporary text files..."

# Convert JSON segments to text files with metadata
SEGMENT_COUNT=0
for file in "$PROCESSED_DIR"/*_segment_*.json; do
    if [ -f "$file" ]; then
        BASENAME=$(basename "$file" .json)
        
        # Extract text content
        TEXT=$(jq -r '.text' "$file")
        
        # Extract metadata as JSON
        METADATA=$(jq -c '.metadata' "$file")
        
        # Create text file
        echo "$TEXT" > "$TEMP_DIR/${BASENAME}.txt"
        
        # Create metadata file (for reference)
        echo "$METADATA" > "$TEMP_DIR/${BASENAME}_metadata.json"
        
        ((SEGMENT_COUNT++))
    fi
done

echo "Created $SEGMENT_COUNT text files"
echo ""

# Upload text files to S3
echo "Uploading to S3..."
aws s3 sync "$TEMP_DIR" "s3://${BUCKET_NAME}/lectures/" \
  --exclude "*_metadata.json" \
  --content-type "text/plain"

# Upload affinity map
if [ -f "$PROCESSED_DIR/affinity_map.json" ]; then
    echo "Uploading affinity map..."
    aws s3 cp "$PROCESSED_DIR/affinity_map.json" \
      "s3://${BUCKET_NAME}/metadata/affinity_map.json"
fi

# Upload master index
if [ -f "$PROCESSED_DIR/master_index.json" ]; then
    echo "Uploading master index..."
    aws s3 cp "$PROCESSED_DIR/master_index.json" \
      "s3://${BUCKET_NAME}/metadata/master_index.json"
fi

# Cleanup
rm -rf "$TEMP_DIR"

echo ""
echo "✓ Upload complete!"
echo ""
echo "Next steps:"
echo "1. Go to AWS Bedrock Console"
echo "2. Navigate to your Knowledge Base"
echo "3. Click 'Sync' to index the new data"
echo "4. Wait for sync to complete (5-10 minutes)"
echo ""
echo "S3 locations:"
echo "  Lectures: s3://${BUCKET_NAME}/lectures/"
echo "  Metadata: s3://${BUCKET_NAME}/metadata/"
