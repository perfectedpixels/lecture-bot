# Bedrock Knowledge Base Setup

Your infrastructure is deployed! Now create the Knowledge Base.

## Your Values

```
Account: 427791004700
Region: us-east-1
Bucket: lecture-transcripts-427791004700
Bedrock Role ARN: arn:aws:iam::427791004700:role/LectureBotStack-BedrockKBRole10C55766-rzguFD8wlHg5
```

## Step 1: Enable Bedrock Models (5 minutes)

1. Go to: https://us-east-1.console.aws.amazon.com/bedrock/home?region=us-east-1#/modelaccess

2. Click "Modify model access" or "Enable specific models"

3. Check these models:
   - ✅ **Anthropic - Claude 3 Sonnet**
   - ✅ **Anthropic - Claude 3 Haiku**  
   - ✅ **Amazon - Titan Embeddings G1 - Text**

4. Click "Request model access" or "Save changes"

5. Wait 1-2 minutes for "Access granted" status

## Step 2: Create Knowledge Base (10 minutes)

1. Go to: https://us-east-1.console.aws.amazon.com/bedrock/home?region=us-east-1#/knowledge-bases

2. Click "Create knowledge base"

### Page 1: Knowledge base details

- **Name**: `LectureBot-KB`
- **Description**: `Knowledge base for Jason Levine's lecture transcripts`
- **IAM Role**: 
  - Select "Use an existing service role"
  - **Role ARN**: `arn:aws:iam::427791004700:role/LectureBotStack-BedrockKBRole10C55766-rzguFD8wlHg5`
- Click "Next"

### Page 2: Set up data source

- **Data source name**: `lecture-transcripts`
- **S3 URI**: `s3://lecture-transcripts-427791004700/lectures/`
  - ⚠️ Make sure to include `/lectures/` at the end!
- **Chunking strategy**: 
  - Select "Default chunking"
  - Max tokens: 300
  - Overlap percentage: 20%
- Click "Next"

### Page 3: Select embeddings model

- **Embeddings model**: `Titan Embeddings G1 - Text`
- **Vector database**: 
  - Select "Quick create a new vector store"
  - This creates OpenSearch Serverless automatically
- Click "Next"

### Page 4: Review and create

- Review all settings
- Click "Create knowledge base"

**Wait**: 2-3 minutes for creation

## Step 3: Get Knowledge Base ID

After creation:
1. You'll see the Knowledge Base details page
2. At the top, copy the **Knowledge Base ID**
   - Format: `XXXXXXXXXX` (10 characters)
   - Example: `AB12CD34EF`

**Save this ID** - you'll need it for the Streamlit app!

## Step 4: Upload Sample Lecture

```bash
cd ~/Dropbox/playground/class\ projects
./scripts/upload_transcript.sh data/sample_lecture.txt "ML_Intro"
```

## Step 5: Sync Data Source

1. In the Knowledge Base page, click "Data sources" tab
2. Select `lecture-transcripts`
3. Click "Sync" button
4. Wait 1-2 minutes
5. Status should show "Available" with file count

## Step 6: Test in Streamlit

1. Open browser: http://localhost:8501
2. In sidebar:
   - Enter **Knowledge Base ID**: `XXXXXXXXXX`
   - Select model: **Claude 3 Sonnet**
   - Click "Connect"
3. Try asking: "What are the three types of machine learning?"

## Troubleshooting

### Models Not Available
- Make sure you enabled model access in Step 1
- Wait a few minutes for approval
- Refresh the page

### Knowledge Base Creation Fails
- Verify the IAM role ARN is correct
- Make sure S3 URI ends with `/lectures/`
- Check you're in us-east-1 region

### Sync Shows 0 Files
- Upload a file first: `./scripts/upload_transcript.sh data/sample_lecture.txt "Test"`
- Then sync again

### Streamlit Can't Connect
- Double-check the Knowledge Base ID
- Make sure it's just the ID, not the full ARN
- Verify AWS credentials are still valid

## Next Steps

Once connected and working:
1. Upload more lecture transcripts
2. Test the persona chat
3. Try the safety rules
4. Process transcripts for concept extraction
