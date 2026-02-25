# Lecture Bot Deployment - Step by Step

Based on your deployment guide experience, adapted for this serverless architecture.

**Time Estimate**: 1-2 hours (mostly AWS setup and waiting)

---

## Prerequisites Check

```bash
# 1. AWS CLI configured
aws sts get-caller-identity

# 2. Node.js installed
node --version  # Should be 18+

# 3. Python installed
python3 --version  # Should be 3.9+

# 4. CDK CLI installed
npm install -g aws-cdk
cdk --version
```

---

## Phase 1: Configure AWS Credentials (15 minutes)

### Option A: Using Access Keys

```bash
aws configure
# Enter:
# - AWS Access Key ID
# - AWS Secret Access Key
# - Default region: us-east-1
# - Default output format: json
```

### Option B: Using Isengard (Amazon Internal)

```bash
# Go to: https://isengard.amazon.com
# Select account → Credentials → bash/zsh tab
# Copy and paste export commands

# Verify
aws sts get-caller-identity
```

**Save these values:**
- Account ID: `XXXXXXXXXXXX`
- Region: `us-east-1` (or your preferred region)

---

## Phase 2: Deploy Infrastructure (30 minutes)

### 2.1 Install Dependencies

```bash
cd infrastructure
npm install --registry https://registry.npmjs.org/
```

### 2.2 Build TypeScript

```bash
npm run build
```

### 2.3 Bootstrap CDK (First Time Only)

```bash
cdk bootstrap aws://ACCOUNT-ID/us-east-1
```

This creates the CDK toolkit stack in your account.

### 2.4 Review What Will Be Created

```bash
cdk synth
```

This shows the CloudFormation template that will be deployed:
- S3 bucket for lecture transcripts
- Lambda function for processing uploads
- IAM roles for Bedrock access

### 2.5 Deploy

```bash
cdk deploy
```

**Approve the changes** when prompted.

**Wait time**: 3-5 minutes

**Save the outputs:**
```
LectureBotStack.BucketName = lecture-transcripts-XXXXXXXXXXXX
LectureBotStack.BedrockRoleArn = arn:aws:iam::XXXXXXXXXXXX:role/LectureBotStack-BedrockKBRole...
```

---

## Phase 3: Create Bedrock Knowledge Base (30 minutes)

### 3.1 Enable Bedrock Models

1. Go to: https://console.aws.amazon.com/bedrock/
2. Click "Model access" in left sidebar
3. Click "Enable specific models"
4. Enable:
   - ✅ Claude 3 Sonnet
   - ✅ Claude 3 Haiku
   - ✅ Titan Embeddings G1 - Text
5. Click "Save changes"

**Wait time**: 1-2 minutes for approval

### 3.2 Create Knowledge Base

1. Go to: https://console.aws.amazon.com/bedrock/
2. Click "Knowledge bases" → "Create knowledge base"

**Step 1: Provide knowledge base details**
- Name: `LectureBot-KB`
- Description: `Knowledge base for lecture transcripts`
- IAM role: Select "Use existing service role"
  - Choose the role from CDK outputs: `LectureBotStack-BedrockKBRole...`
- Click "Next"

**Step 2: Set up data source**
- Data source name: `lecture-transcripts`
- S3 URI: `s3://lecture-transcripts-XXXXXXXXXXXX/lectures/`
  (Use bucket name from CDK outputs)
- Chunking strategy: Default (300 tokens, 20% overlap)
- Click "Next"

**Step 3: Select embeddings model**
- Embeddings model: `Titan Embeddings G1 - Text`
- Vector database: "Quick create a new vector store"
  - This creates an OpenSearch Serverless collection automatically
- Click "Next"

**Step 4: Review and create**
- Review settings
- Click "Create knowledge base"

**Wait time**: 2-3 minutes

**Save the Knowledge Base ID**: `XXXXXXXXXX` (shown at top of page)

### 3.3 Sync Data Source

After creation:
1. Click on your knowledge base
2. Go to "Data source" tab
3. Click "Sync" button

**Note**: First sync will be empty (no files yet). We'll upload files next.

---

## Phase 4: Upload Lecture Transcripts (10 minutes)

### 4.1 Test with Sample Lecture

```bash
cd ..  # Back to project root
chmod +x scripts/upload_transcript.sh

# Upload sample
./scripts/upload_transcript.sh data/sample_lecture.txt "ML_Intro"
```

### 4.2 Upload Your Actual Lectures

**Option A: Single file**
```bash
./scripts/upload_transcript.sh path/to/lecture.txt "Lecture_Name"
```

**Option B: Bulk upload**
```bash
# Upload all files in a directory
aws s3 sync ./my-lectures/ s3://lecture-transcripts-XXXXXXXXXXXX/lectures/
```

### 4.3 Sync Knowledge Base

After uploading files:
1. Go back to Bedrock Console → Knowledge bases
2. Click your knowledge base
3. Go to "Data source" tab
4. Click "Sync"

**Wait time**: 1-5 minutes depending on file count

**Verify**: Status should show "Available" with file count

---

## Phase 5: Test the Bot (5 minutes)

### 5.1 Update Streamlit App

The app should still be running at `http://localhost:8501`

If not:
```bash
cd app
source venv/bin/activate
streamlit run streamlit_app_simple.py
```

### 5.2 Connect to Knowledge Base

1. Open browser: `http://localhost:8501`
2. In sidebar:
   - Enter Knowledge Base ID: `XXXXXXXXXX`
   - Select model: `Claude 3 Sonnet`
   - Click "Connect"

### 5.3 Test Chat

Try these questions:
- "What are the three types of machine learning?"
- "Explain supervised learning"
- "Tell me about your experience at AWS"

### 5.4 Test Safety Rules

Go to **🧪 Test Safety** tab and try:
- ✅ "What is user-centered design?" (should work)
- 🛡️ "What's your phone number?" (should block)
- 🛡️ "How can I cheat?" (should block)

---

## Phase 6: Preprocess Your Transcripts (Optional, 20 minutes)

If your transcripts have timestamps and speaker names:

### 6.1 Use Preprocessing Tab

1. Go to **🔧 Preprocess** tab
2. Upload raw transcript
3. Enter speaker name: "Jason Levine"
4. Check "Remove timestamps"
5. Check "Extract and tag concepts"
6. Click "Process Transcript"

### 6.2 Download Cleaned Files

- Download cleaned text
- Download concepts JSON
- Download chunks JSON

### 6.3 Upload Cleaned Transcripts

```bash
./scripts/upload_transcript.sh cleaned_lecture.txt "Lecture_Name_Cleaned"
```

### 6.4 Sync Knowledge Base Again

Bedrock Console → Knowledge bases → Sync

---

## Troubleshooting

### AWS Credentials Expired

**Symptoms**: `ExpiredToken` error

**Solution**:
```bash
# Refresh Isengard credentials
# Or run: aws configure
```

### CDK Deploy Fails

**Error**: "Need to perform AWS calls for account XXXX, but no credentials configured"

**Solution**:
```bash
aws sts get-caller-identity  # Verify credentials
cdk bootstrap  # Re-bootstrap if needed
```

### Knowledge Base Not Finding Content

**Symptoms**: Bot says "I don't have information about that"

**Causes**:
1. Files not uploaded to S3
2. Data source not synced
3. Files not in `/lectures/` prefix

**Solutions**:
```bash
# Check files in S3
aws s3 ls s3://lecture-transcripts-XXXXXXXXXXXX/lectures/

# Re-sync data source
# Bedrock Console → Knowledge bases → Sync
```

### Streamlit Import Errors

**Error**: `ModuleNotFoundError: No module named 'boto3'`

**Solution**:
```bash
cd app
source venv/bin/activate
pip install -r requirements.txt
```

### Bot Responses Are Generic

**Symptoms**: Bot doesn't use persona or professional background

**Cause**: Using old bot version

**Solution**: Make sure `streamlit_app_simple.py` imports `persona_bot_safe`:
```python
from persona_bot_safe import PersonaBot
```

---

## Production Checklist

Before sharing with students:

- [ ] AWS credentials configured
- [ ] CDK stack deployed successfully
- [ ] Bedrock models enabled (Claude, Titan)
- [ ] Knowledge Base created
- [ ] IAM role attached to Knowledge Base
- [ ] Lecture transcripts uploaded to S3
- [ ] Data source synced (shows file count)
- [ ] Streamlit app connects successfully
- [ ] Test questions return relevant answers
- [ ] Safety rules trigger appropriately
- [ ] Persona responds authentically
- [ ] Source citations appear in responses

---

## Cost Estimate

For moderate use (100 queries/day, 50 lectures):

| Service | Monthly Cost |
|---------|--------------|
| S3 Storage (10GB) | ~$0.25 |
| Lambda (processing) | ~$0.50 |
| Bedrock Knowledge Base | ~$5-10 |
| OpenSearch Serverless | ~$20-30 |
| Bedrock Model Usage (Claude) | ~$10-20 |
| **Total** | **~$35-60/month** |

**Note**: Costs scale with:
- Number of queries
- Length of responses
- Number of lectures
- Storage size

---

## Next Steps

### Enhance the Bot

1. **Add More Lectures**
   - Upload all your course transcripts
   - Sync Knowledge Base after each batch

2. **Build Affinity Map**
   - Process all transcripts through preprocessing
   - Generate concept clusters
   - Upload affinity_map.json to Streamlit

3. **Customize Persona**
   - Edit `src/persona_bot_safe.py`
   - Update `PROFESSIONAL_CONTEXT`
   - Add more safety rules if needed

4. **Share with Students**
   - Deploy Streamlit to EC2 or Streamlit Cloud
   - Provide Knowledge Base ID
   - Share usage guidelines

### Deploy Streamlit Publicly (Optional)

If you want students to access without running locally:

**Option A: Streamlit Cloud** (Easiest)
1. Push code to GitHub
2. Go to: https://streamlit.io/cloud
3. Connect repository
4. Deploy

**Option B: EC2** (More control)
- Follow your SuperNova deployment guide
- Use nginx reverse proxy
- Set up domain

---

## Resources

- **AWS Bedrock Console**: https://console.aws.amazon.com/bedrock/
- **S3 Console**: https://console.aws.amazon.com/s3/
- **CloudFormation**: https://console.aws.amazon.com/cloudformation/
- **Streamlit Docs**: https://docs.streamlit.io/

---

## Quick Commands Reference

```bash
# Deploy infrastructure
cd infrastructure && cdk deploy

# Upload transcript
./scripts/upload_transcript.sh file.txt "Name"

# Check S3 files
aws s3 ls s3://lecture-transcripts-XXXXXXXXXXXX/lectures/

# Run Streamlit
cd app && streamlit run streamlit_app_simple.py

# Refresh AWS credentials (Isengard)
# Copy from: https://isengard.amazon.com

# Check CDK stack status
aws cloudformation describe-stacks --stack-name LectureBotStack
```

---

**Ready to deploy?** Start with Phase 1!
