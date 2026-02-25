# Create Bedrock Knowledge Base via Console

The automated script hit some OpenSearch index issues. The AWS Console is simpler for first-time setup.

## Step-by-Step Instructions

### 1. Go to Bedrock Console
Open: https://console.aws.amazon.com/bedrock/home?region=us-east-1#/knowledge-bases

### 2. Click "Create knowledge base"

### 3. Knowledge Base Details
- Name: `LectureBot-KB`
- Description: `Knowledge base for lecture transcripts`
- IAM Role: **Select "Use an existing service role"**
  - Role ARN: `arn:aws:iam::427791004700:role/LectureBotStack-BedrockKBRole10C55766-rzguFD8wlHg5`
- Click "Next"

### 4. Data Source
- Data source name: `S3-Lectures`
- S3 URI: `s3://lecture-transcripts-427791004700/lectures/`
- Click "Next"

### 5. Embeddings Model
- Embeddings model: **Titan Embeddings G1 - Text v2.0**
- Click "Next"

### 6. Vector Database
- Select: **Quick create a new vector store**
  - This will automatically create an OpenSearch Serverless collection
- Click "Next"

### 7. Review and Create
- Review all settings
- Click "Create knowledge base"

### 8. Sync Data Source
- After creation, you'll see your knowledge base
- Click on the data source "S3-Lectures"
- Click "Sync" button
- Wait 1-2 minutes for sync to complete

### 9. Get Knowledge Base ID
- On the knowledge base page, copy the **Knowledge Base ID**
- It looks like: `XXXXXXXXXX` (10 characters)

### 10. Use in Streamlit App
- Go back to your Streamlit app (http://localhost:8501)
- Paste the Knowledge Base ID in the sidebar
- Click "Connect"
- Start asking questions!

## Already Have Resources?

We already created:
- ✅ S3 Bucket: `lecture-transcripts-427791004700`
- ✅ IAM Role for Bedrock
- ✅ Sample lecture uploaded
- ✅ OpenSearch collection: `lecture-bot-kb` (you can reuse or let Bedrock create new)

If you want to use the existing OpenSearch collection:
- In step 6, choose "Select an existing vector store"
- Collection: `lecture-bot-kb`
- But "Quick create" is easier and recommended!

## Troubleshooting

**Can't find Bedrock in console?**
- Make sure you're in us-east-1 region (top right)

**IAM role not found?**
- Use the full ARN provided above
- Or choose "Create and use a new service role"

**Sync fails?**
- Check S3 bucket has files in `lectures/` prefix
- Verify IAM role has S3 read permissions (it should)

## Next Steps

Once you have the Knowledge Base ID:
1. Enter it in the Streamlit app
2. Try asking: "What are the three types of machine learning?"
3. Upload more lectures to S3
4. Sync the data source again to index new content
