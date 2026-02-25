# Deployment Guide

## Prerequisites

- AWS CLI configured with appropriate credentials
- Node.js 18+ and npm
- Python 3.11+
- AWS CDK CLI: `npm install -g aws-cdk`

## Step 1: Deploy Infrastructure

```bash
cd infrastructure
npm install
npm run build
cdk bootstrap  # First time only
cdk deploy
```

Note the outputs: `BucketName` and `BedrockRoleArn`

## Step 2: Setup Bedrock Knowledge Base

Run the helper script to see instructions:
```bash
chmod +x scripts/setup_bedrock_kb.sh
./scripts/setup_bedrock_kb.sh
```

Or manually:
1. Go to AWS Bedrock Console
2. Create Knowledge Base with the S3 bucket as data source
3. Use the IAM role from stack outputs
4. Choose embedding model (recommend: amazon.titan-embed-text-v1)
5. Sync the data source

## Step 3: Upload Lecture Transcripts

```bash
chmod +x scripts/upload_transcript.sh
./scripts/upload_transcript.sh data/sample_lecture.txt "ML Intro"
```

## Step 4: Query Your Bot

```bash
pip install boto3
python src/query_bot.py <knowledge-base-id> "What is supervised learning?"
```

## Next Steps

- Build a web interface (Flask, FastAPI, or React)
- Add audio transcription pipeline (AWS Transcribe)
- Implement assignment analysis features
- Create visualization dashboard
