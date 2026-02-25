#!/bin/bash

# Test your setup before launching the interface
# Usage: ./test_setup.sh <knowledge-base-id>

if [ $# -lt 1 ]; then
    echo "Usage: $0 <knowledge-base-id>"
    exit 1
fi

KB_ID=$1

echo "=== Testing Lecture Bot Setup ==="
echo ""

# Test 1: AWS Credentials
echo "1. Checking AWS credentials..."
if aws sts get-caller-identity > /dev/null 2>&1; then
    echo "   ✓ AWS credentials configured"
else
    echo "   ✗ AWS credentials not found"
    exit 1
fi

# Test 2: Stack deployed
echo "2. Checking CloudFormation stack..."
if aws cloudformation describe-stacks --stack-name LectureBotStack > /dev/null 2>&1; then
    echo "   ✓ Stack deployed"
    BUCKET=$(aws cloudformation describe-stacks --stack-name LectureBotStack --query "Stacks[0].Outputs[?OutputKey=='BucketName'].OutputValue" --output text)
    echo "   Bucket: $BUCKET"
else
    echo "   ✗ Stack not found. Run: cd infrastructure && cdk deploy"
    exit 1
fi

# Test 3: Knowledge Base exists
echo "3. Checking Knowledge Base..."
if aws bedrock-agent get-knowledge-base --knowledge-base-id "$KB_ID" > /dev/null 2>&1; then
    echo "   ✓ Knowledge Base found"
else
    echo "   ✗ Knowledge Base not found. Check the ID or create one in AWS Console"
    exit 1
fi

# Test 4: S3 bucket has content
echo "4. Checking for lecture files..."
FILE_COUNT=$(aws s3 ls "s3://${BUCKET}/lectures/" --recursive | wc -l)
if [ "$FILE_COUNT" -gt 0 ]; then
    echo "   ✓ Found $FILE_COUNT file(s) in S3"
else
    echo "   ⚠ No files found. Upload lectures with: ./scripts/upload_transcript.sh"
fi

# Test 5: Python dependencies
echo "5. Checking Python environment..."
if python3 -c "import boto3, streamlit" 2>/dev/null; then
    echo "   ✓ Python dependencies installed"
else
    echo "   ⚠ Missing dependencies. Run: cd app && pip install -r requirements.txt"
fi

echo ""
echo "=== Setup Test Complete ==="
echo ""
echo "To launch the interface:"
echo "  cd app && ./run.sh"
echo ""
echo "Or test via CLI:"
echo "  python src/query_bot.py $KB_ID 'What is machine learning?'"
