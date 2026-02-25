# Lecture Bot - AI-Powered Learning Assistant

Transform your lecture transcripts into an intelligent chatbot that embodies your teaching persona, understands concept relationships, and provides contextual responses.

## 🎯 What Makes This Special

- 🎭 **Persona Mode**: Bot responds as the instructor, using first person and teaching style
- 🧠 **Concept Clustering**: Automatically discovers relationships between topics via affinity mapping
- 🎯 **Context-Aware**: Uses concept clusters to retrieve the most relevant lecture segments
- 📚 **Source Attribution**: Every answer cites specific lectures
- 📊 **Assignment Analysis**: Provides instructor-style feedback on student work

## ✨ Features

- 💬 **Interactive Q&A**: Natural conversation with your lecture persona
- 📄 **Report Generation**: Comprehensive summaries on any topic
- 📊 **Content Analysis**: Concept maps, key takeaways, assignment feedback
- 🔍 **Smart Search**: Vector + concept-based semantic search
- 🎨 **Affinity Mapping**: Visual concept relationships across all lectures

## 🚀 Quick Start

### Option A: Complete Workflow (Recommended)

See [COMPLETE_WORKFLOW.md](COMPLETE_WORKFLOW.md) for the full guide.

```bash
# 1. Preprocess your transcripts
./scripts/preprocess_lectures.sh raw_transcripts/ processed_lectures/

# 2. Deploy infrastructure
cd infrastructure && npm install && cdk deploy

# 3. Upload to S3 and create Knowledge Base
./scripts/upload_processed_to_s3.sh processed_lectures/

# 4. Launch interface
cd app && ./run.sh
```

### Option B: Quick Test (Sample Data)

```bash
# 1. Deploy infrastructure
cd infrastructure && npm install && cdk deploy

# 2. Upload sample lecture
./scripts/upload_transcript.sh data/sample_lecture.txt "ML_Intro"

# 3. Create Knowledge Base in AWS Console (see QUICKSTART.md)

# 4. Launch interface
cd app && ./run.sh
```

## 📋 Prerequisites

- AWS account with Bedrock access
- Python 3.11+
- Node.js 18+
- AWS CLI configured

## 🏗️ Architecture

```
Raw Transcripts → Preprocessing Pipeline → S3 Bucket
                       ↓                      ↓
                  Affinity Map          Bedrock KB
                       ↓                      ↓
                  Persona Bot ← OpenSearch Serverless
                       ↓
                 Streamlit UI
```

**Key Components:**
- **Preprocessing**: Cleans transcripts, extracts concepts, creates affinity map
- **Bedrock KB**: Vector search with metadata filtering
- **Persona Bot**: Concept-aware context selection + persona prompting
- **Streamlit UI**: Interactive web interface

See [ARCHITECTURE.md](ARCHITECTURE.md) for detailed architecture.

## 📁 Project Structure

```
/infrastructure          - AWS CDK infrastructure code
/src
  /preprocessing        - Transcript cleaning, concept extraction, affinity mapping
  persona_bot.py        - Enhanced bot with persona and concept awareness
  query_bot.py          - Basic RAG bot (legacy)
/app                    - Streamlit web interface
/data                   - Sample lecture transcripts
/scripts                - Helper scripts for preprocessing and upload
```

## 📚 Documentation

- [COMPLETE_WORKFLOW.md](COMPLETE_WORKFLOW.md) - Full end-to-end guide
- [PREPROCESSING_GUIDE.md](PREPROCESSING_GUIDE.md) - Transcript preprocessing details
- [QUICKSTART.md](QUICKSTART.md) - 15-minute basic setup
- [DEPLOYMENT.md](DEPLOYMENT.md) - Infrastructure deployment
- [ARCHITECTURE.md](ARCHITECTURE.md) - System architecture and design

## 💰 Cost Estimate

For moderate use (100 queries/day):
- S3: ~$0.50/month
- Bedrock KB: ~$5-10/month
- OpenSearch Serverless: ~$20-30/month
- Lambda: <$1/month
- Claude API calls: ~$10-20/month

**Total: ~$35-60/month**

## 🎓 How It Works

### 1. Preprocessing
- Removes timestamps and speaker labels ("Jason Levine:")
- Segments into meaningful chunks
- Extracts concepts using Claude
- Creates affinity map of concept relationships

### 2. Concept Clustering
- Builds co-occurrence matrix (which concepts appear together)
- Creates semantic clusters using Claude
- Calculates affinity scores

### 3. Query Processing
- Analyzes user question
- Identifies relevant concept clusters
- Retrieves segments with concept filtering
- Generates persona-based response

### 4. Persona Layer
- Responds in first person as instructor
- References specific lectures
- Maintains consistent teaching style
- Provides contextual examples

## 🔧 Customization

### Change Persona Style
Edit `src/persona_bot.py`:
```python
persona_prompt = f"""You are {self.persona_name}...
YOUR CUSTOM INSTRUCTIONS HERE
```

### Adjust Concept Categories
Edit `src/preprocessing/concept_extractor.py`:
```python
self.categories = [
    "Your Category 1",
    "Your Category 2",
]
```

### Modify Clustering
Edit `src/preprocessing/affinity_mapper.py`:
```python
num_clusters = 10  # Adjust cluster count
```

## 🐛 Troubleshooting

See individual documentation files for detailed troubleshooting:
- Preprocessing issues → [PREPROCESSING_GUIDE.md](PREPROCESSING_GUIDE.md)
- Deployment issues → [DEPLOYMENT.md](DEPLOYMENT.md)
- Runtime issues → [COMPLETE_WORKFLOW.md](COMPLETE_WORKFLOW.md)

## 🚦 Next Steps

After basic setup:
1. Process your actual lecture transcripts
2. Customize the persona prompt
3. Adjust concept categories for your domain
4. Add visualizations for concept clusters
5. Build API wrapper for programmatic access

## 📄 License

MIT License - See LICENSE file for details
