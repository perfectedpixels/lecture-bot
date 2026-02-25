# Multi-Course Setup - Single KB Approach

## Architecture Decision

✅ **Single Knowledge Base** with multiple data sources
✅ Shared lecture transcripts for both courses
✅ Course-specific Canvas content (assignments, policies)
✅ Shared CV for professional context

## Current Status

✅ Streamlit interface has course selector
✅ Canvas content extracted for both courses
✅ Content uploaded to S3 in separate folders
⏳ Need to add 3 more data sources to KB `1TTBVE6MG2`

## S3 Structure

```
s3://lecture-transcripts-427791004700/
├── lectures/              ← Already in KB (shared by both courses)
├── jason_levine-cv.txt    ← Need to add to KB
├── commld-515/            ← Need to add to KB (COMMLD 515 specific)
└── commld-512/            ← Need to add to KB (COMMLD 512 specific)
```

## Next Steps

### 1. Refresh AWS Credentials

Your credentials have expired. Run:

```bash
aws configure
# Enter your Access Key ID and Secret Access Key
# Region: us-east-1
# Format: json

# Verify
aws sts get-caller-identity
```

### 2. Add Data Sources to Knowledge Base

Go to: https://us-east-1.console.aws.amazon.com/bedrock/home?region=us-east-1#/knowledge-bases/1TTBVE6MG2

For each data source below:

**A. Add CV (jason_levine-cv.txt)**
- Click "Add data source"
- Name: `CV-Professional-Background`
- S3 URI: `s3://lecture-transcripts-427791004700/jason_levine-cv.txt`
- Click "Add"

**B. Add COMMLD 515 Content**
- Click "Add data source"
- Name: `COMMLD-515-Canvas`
- S3 URI: `s3://lecture-transcripts-427791004700/commld-515/`
- Click "Add"

**C. Add COMMLD 512 Content**
- Click "Add data source"
- Name: `COMMLD-512-Canvas`
- S3 URI: `s3://lecture-transcripts-427791004700/commld-512/`
- Click "Add"

### 3. Sync All Data Sources

After adding all 3 data sources:
1. Go to "Data sources" tab
2. For each data source, click "Sync"
3. Wait for all to show "Available" status (1-2 min each)

### 4. Test Both Courses

Restart Streamlit if needed:
```bash
cd app
source venv/bin/activate
streamlit run streamlit_app_simple.py
```

Test queries:
- **COMMLD 515**: "What are the course policies?" or "Tell me about the assignments"
- **COMMLD 512**: "What is the sample usability script?" or "What's the user research project?"

## How It Works

**Single KB Benefits**:
- Shared lecture content (both courses use same lectures)
- Shared professional context (CV)
- Course-specific assignments stay separate
- Simpler to maintain

**No Cross-Contamination**:
- Bot retrieves relevant chunks from all data sources
- S3 folder structure keeps assignments separate
- Course selector provides student context in queries
- Natural language understanding finds correct course content

## File Locations

**Shared Content** (both courses):
- Lectures: `s3://lecture-transcripts-427791004700/lectures/`
- CV: `s3://lecture-transcripts-427791004700/jason_levine-cv.txt`

**COMMLD 515 Content**:
- Local: `data/canvas_extracted/` (33 files)
- S3: `s3://lecture-transcripts-427791004700/commld-515/`

**COMMLD 512 Content**:
- Local: `data/canvas_extracted_512/` (33 files)
- S3: `s3://lecture-transcripts-427791004700/commld-512/`

**Knowledge Base**: `1TTBVE6MG2` (single KB for all content)

## Troubleshooting

**Q: Will students see assignments from the other course?**
A: No. The bot retrieves relevant chunks based on the query. Course-specific content is naturally separated by folder structure and content.

**Q: Should I use the second KB I created (TKGHP6IFEH)?**
A: No, you can delete it. Single KB approach is simpler and allows shared lecture content.

**Q: How do I verify no cross-contamination?**
A: Test with course-specific queries like "What's the usability script?" (512 only) and check the sources returned.
