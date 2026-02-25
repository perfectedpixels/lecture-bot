# Complete Workflow: Building Your Persona Chatbot

This guide walks you through the entire process of creating a chatbot based on your lecture transcripts.

## Overview

You'll build a chatbot that:
- Embodies your teaching persona
- Uses concept clustering for intelligent context selection
- Provides source attribution
- Can analyze assignments and generate reports

## Phase 1: Prepare Your Transcripts

### Step 1: Collect Raw Transcripts

Put all your lecture transcripts in a folder:
```
raw_transcripts/
├── lecture_01_intro_to_ai.txt
├── lecture_02_ml_basics.txt
├── lecture_03_design_thinking.txt
└── ...
```

Transcripts can include timestamps and speaker labels - they'll be cleaned automatically.

### Step 2: Run Preprocessing Pipeline

```bash
# Make script executable
chmod +x scripts/preprocess_lectures.sh

# Process all lectures
./scripts/preprocess_lectures.sh raw_transcripts/ processed_lectures/
```

This will:
1. Remove timestamps and "Jason Levine:" labels
2. Break into semantic segments
3. Extract concepts using Claude
4. Create affinity map of concept relationships

Output:
```
processed_lectures/
├── master_index.json           # Overview
├── affinity_map.json          # Concept clusters
├── lecture_01_segment_1.json  # Individual segments
├── lecture_01_segment_2.json
└── ...
```

**Time estimate:** 2-5 minutes per lecture (depends on length)

## Phase 2: Deploy AWS Infrastructure

### Step 1: Configure AWS Credentials

```bash
aws configure
# Enter your Access Key ID and Secret Access Key
# Region: us-east-1 (recommended for Bedrock)
```

### Step 2: Deploy with CDK

```bash
cd infrastructure
npm install --registry https://registry.npmjs.org/
npm run build
cdk bootstrap  # First time only
cdk deploy
```

Save the outputs:
- `BucketName`: Your S3 bucket
- `BedrockRoleArn`: IAM role for Bedrock

**Time estimate:** 5-10 minutes

## Phase 3: Setup Bedrock Knowledge Base

### Step 1: Upload Processed Segments to S3

```bash
# Get bucket name from CDK output
BUCKET_NAME=$(aws cloudformation describe-stacks \
  --stack-name LectureBotStack \
  --query "Stacks[0].Outputs[?OutputKey=='BucketName'].OutputValue" \
  --output text)

# Upload segments (text content only)
for file in processed_lectures/*_segment_*.json; do
  # Extract just the text field for Bedrock KB
  TEXT=$(jq -r '.text' "$file")
  METADATA=$(jq -r '.metadata' "$file")
  
  # Create text file with metadata
  BASENAME=$(basename "$file" .json)
  echo "$TEXT" > "temp_${BASENAME}.txt"
  
  # Upload with metadata
  aws s3 cp "temp_${BASENAME}.txt" \
    "s3://${BUCKET_NAME}/lectures/${BASENAME}.txt" \
    --metadata "$(echo $METADATA | jq -r 'to_entries | map("\(.key)=\(.value)") | join(",")')"
  
  rm "temp_${BASENAME}.txt"
done

# Upload affinity map separately
aws s3 cp processed_lectures/affinity_map.json \
  s3://${BUCKET_NAME}/metadata/affinity_map.json
```

### Step 2: Create Knowledge Base in AWS Console

1. Go to [AWS Bedrock Console](https://console.aws.amazon.com/bedrock/)
2. Navigate to **Knowledge bases** → **Create knowledge base**
3. Configure:
   - **Name:** `LectureBot-KB`
   - **IAM role:** Select the `BedrockRoleArn` from CDK output
4. Add data source:
   - **Type:** S3
   - **S3 URI:** `s3://<BucketName>/lectures/`
   - **Chunking strategy:** Default (or Fixed size: 300 tokens, 20% overlap)
5. Configure embeddings:
   - **Model:** `Titan Embeddings G1 - Text`
   - **Vector database:** Create new OpenSearch Serverless collection
6. **Review and create**
7. Click **Sync** to index your data
8. **Copy the Knowledge Base ID** (you'll need this)

**Time estimate:** 10-15 minutes (plus 5-10 min for sync)

## Phase 4: Launch the Interface

### Step 1: Download Affinity Map

```bash
# Download affinity map from S3
aws s3 cp s3://${BUCKET_NAME}/metadata/affinity_map.json \
  processed_lectures/affinity_map.json
```

### Step 2: Start Streamlit App

```bash
cd app
./run.sh
```

Opens at `http://localhost:8501`

### Step 3: Configure in UI

1. Enter your **Knowledge Base ID** (from Phase 3, Step 2)
2. Upload **affinity_map.json** (from processed_lectures/)
3. Enable **Persona Mode**
4. Set **Instructor Name** (e.g., "Professor Levine")
5. Click **Connect**

**Time estimate:** 2 minutes

## Phase 5: Test Your Bot

### Test Questions

Try these to verify everything works:

1. **Basic Q&A:**
   - "What did you teach about machine learning?"
   - "Explain the design thinking process"

2. **Persona Check:**
   - Should respond in first person: "In my lectures, I discussed..."
   - Should reference specific lectures

3. **Concept Awareness:**
   - Check "Relevant Concepts" in expanded section
   - Should show related concepts from affinity map

4. **Assignment Analysis:**
   - Go to Analysis tab → Assignment Improvement
   - Paste sample assignment
   - Should get feedback in instructor's voice

### Expected Behavior

✓ Responses use first person ("I taught", "In my lectures")
✓ Relevant concepts shown for each answer
✓ Source attribution to specific lecture segments
✓ Consistent teaching style across responses

## Maintenance & Updates

### Adding New Lectures

1. Add new transcript to `raw_transcripts/`
2. Run preprocessing:
   ```bash
   python3 src/preprocessing/pipeline.py \
     raw_transcripts/new_lecture.txt \
     processed_lectures/
   ```
3. Upload new segments to S3
4. Sync Knowledge Base in AWS Console
5. Regenerate affinity map:
   ```bash
   python3 src/preprocessing/pipeline.py \
     raw_transcripts/ \
     processed_lectures/
   ```
6. Upload new affinity_map.json to S3
7. Re-upload in Streamlit UI

### Updating Persona

Edit `src/persona_bot.py`:
```python
def _build_persona_prompt(self, question: str, context: str, concepts: List[str] = None) -> str:
    persona_prompt = f"""You are {self.persona_name}, responding to a student's question.

    YOUR CUSTOM INSTRUCTIONS HERE:
    - Use specific teaching style
    - Reference particular frameworks
    - Include personal anecdotes
    ...
```

## Troubleshooting

### "No relevant concepts found"
- Check that affinity_map.json is uploaded
- Verify preprocessing completed successfully
- Try disabling persona mode temporarily

### "Knowledge Base returns no results"
- Verify KB is synced (check AWS Console)
- Check S3 bucket has files in `lectures/` prefix
- Try broader questions first

### "Responses don't sound like me"
- Adjust persona prompt in `persona_bot.py`
- Add more specific teaching style instructions
- Include example responses in prompt

### "Concepts not clustering well"
- Adjust number of clusters in `affinity_mapper.py`
- Review concept categories in `concept_extractor.py`
- Try reprocessing with different segment sizes

## Cost Breakdown

Monthly costs for moderate use (100 queries/day):

- **S3:** ~$0.50 (storage)
- **Bedrock Knowledge Base:** ~$5-10 (queries)
- **OpenSearch Serverless:** ~$20-30 (vector storage)
- **Lambda:** <$1 (processing)
- **Bedrock Model Calls:** ~$10-20 (Claude usage)

**Total:** ~$35-60/month

## Next Steps

1. **Customize persona** - Edit prompts to match your teaching style
2. **Add visualizations** - Create concept map UI in Streamlit
3. **Build API** - Wrap in FastAPI for programmatic access
4. **Mobile interface** - Create React Native app
5. **Analytics** - Track which concepts students ask about most

## Support

- Preprocessing issues: See `PREPROCESSING_GUIDE.md`
- Deployment issues: See `DEPLOYMENT.md`
- Quick start: See `QUICKSTART.md`
