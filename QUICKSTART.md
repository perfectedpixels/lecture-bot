# Quick Start Guide

Get your Lecture Bot running in 15 minutes.

## 1. Deploy Infrastructure (5 min)

```bash
cd infrastructure
npm install
npm run build
cdk bootstrap  # First time only
cdk deploy
```

Save the outputs: `BucketName` and `BedrockRoleArn`

## 2. Create Bedrock Knowledge Base (5 min)

### Option A: AWS Console (Recommended for first time)
1. Go to [AWS Bedrock Console](https://console.aws.amazon.com/bedrock/)
2. Navigate to "Knowledge bases" → "Create knowledge base"
3. Configure:
   - Name: `LectureBot-KB`
   - IAM role: Use the `BedrockRoleArn` from step 1
4. Add data source:
   - Type: S3
   - S3 URI: `s3://<BucketName>/lectures/`
   - Chunking: Default (300 tokens, 20% overlap)
5. Configure embeddings:
   - Model: `Titan Embeddings G1 - Text`
   - Vector database: Create new OpenSearch Serverless collection
6. Review and create
7. Click "Sync" to index data
8. Copy the Knowledge Base ID (you'll need this)

### Option B: AWS CLI
```bash
# Coming soon - automated setup script
```

## 3. Upload Sample Lecture (2 min)

```bash
chmod +x scripts/upload_transcript.sh
./scripts/upload_transcript.sh data/sample_lecture.txt "ML_Intro"
```

Wait 1-2 minutes, then sync the Knowledge Base:
```bash
aws bedrock-agent start-ingestion-job \
  --knowledge-base-id <your-kb-id> \
  --data-source-id <your-data-source-id>
```

## 4. Launch Interface (3 min)

```bash
cd app
chmod +x run.sh
./run.sh
```

The app will open at `http://localhost:8501`

### First Use:
1. Enter your Knowledge Base ID in the sidebar
2. Click "Connect"
3. Start asking questions!

## Example Questions to Try

- "What are the three types of machine learning?"
- "Explain supervised learning with examples"
- "What's the difference between overfitting and underfitting?"
- "Generate a report on machine learning fundamentals"

## Uploading Your Lectures

### Text files:
```bash
./scripts/upload_transcript.sh path/to/lecture.txt "Lecture_Name"
```

### Bulk upload:
```bash
aws s3 sync ./my-lectures/ s3://<BucketName>/lectures/
```

After uploading, sync the Knowledge Base in the AWS Console or via CLI.

## Troubleshooting

**"Knowledge Base not found"**
- Double-check the KB ID
- Ensure it's in the same AWS region

**"No results found"**
- Make sure you synced the data source after uploading
- Check that files are in the `lectures/` prefix

**"Access denied"**
- Verify AWS credentials: `aws sts get-caller-identity`
- Check IAM permissions for Bedrock

## Cost Estimate

For moderate use (100 queries/day):
- S3: ~$0.50/month
- Bedrock Knowledge Base: ~$5-10/month
- OpenSearch Serverless: ~$20-30/month
- Lambda: <$1/month

Total: ~$25-40/month

## Next Steps

- Add more lectures
- Try the Reports tab for comprehensive summaries
- Use Analysis tab for assignment feedback
- Customize the interface in `app/streamlit_app.py`
