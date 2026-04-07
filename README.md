# Lecture Bot - AI-Powered Learning Assistant

Transform lecture transcripts into an intelligent chatbot that embodies the instructor's persona, understands concept relationships, and provides contextual responses.

## What It Does

- **Persona Mode**: Bot responds as the instructor in first person, using their teaching style
- **Concept Clustering**: Automatically discovers relationships between topics via affinity mapping
- **Context-Aware RAG**: Uses semantic search to retrieve the most relevant lecture segments
- **Source Attribution**: Every answer cites specific lecture sources
- **Learning Cards**: Follow-up suggestions, related concepts, and portfolio examples
- **Assignment Analysis**: Instructor-style feedback on student work
- **Voice Output**: Optional text-to-speech via ElevenLabs

## Architecture

```
Streamlit UI
    |
    +---> PersonaBot (Anthropic SDK - Claude API)
    |         |
    |         +---> ChromaDB (local vector search for RAG)
    |         +---> Affinity Map (concept clusters, local JSON)
    |
    +---> LearningCardGenerator (Anthropic SDK)
    +---> PreprocessingPipeline (Anthropic SDK)
    +---> Local filesystem (data/ directory)
```

Everything runs locally. No cloud infrastructure required. The only external call is to the Anthropic API for Claude.

### Why This Architecture

The previous version used 6 AWS services (Bedrock, S3, Lambda, OpenSearch Serverless, CDK, IAM). That meant:

- **$35-60/month** in fixed costs even with zero usage (OpenSearch Serverless alone was $20-30/mo)
- AWS account setup, IAM roles, CDK deployment, Knowledge Base configuration
- Credentials management across multiple services
- Tightly coupled code that was hard to modify or run locally

The current version replaces all of that with:

| Before (AWS) | After (Local) | Why it's better |
|---|---|---|
| Bedrock Runtime | Anthropic Python SDK | Direct API, simpler code, no AWS account needed |
| Bedrock KB + OpenSearch | ChromaDB (embedded) | Single `pip install`, runs in-process, no server |
| S3 | Local filesystem | Data already lives on disk, zero config |
| Lambda | Deleted | Preprocessing already runs locally |
| CDK / CloudFormation | Deleted | No infrastructure to manage |

**Cost**: Pay-per-use only (~$0.03/query). $0/month when idle. For a class of 20-30 students, expect $10-30/month during active use.

## Quick Start

### Prerequisites

- Python 3.11+
- An [Anthropic API key](https://console.anthropic.com/)

### Setup

```bash
# 1. Clone and install
git clone <repo-url>
cd lecture-bot
pip install -r requirements.txt

# 2. Set your API key
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
# Edit .streamlit/secrets.toml and add your ANTHROPIC_API_KEY

# 3. Index lecture data into the local vector database
python scripts/ingest_to_chromadb.py

# 4. Run the app
streamlit run app/streamlit_app_redesign.py
```

Open http://localhost:8501 and start asking questions.

### Adding Your Own Lectures

1. Place `.txt` transcript files in a directory (e.g., `data/my_lectures/`)
2. Index them: `python scripts/ingest_to_chromadb.py data/my_lectures/`
3. Restart the app

## Project Structure

```
src/
  llm_client.py              - Anthropic SDK wrapper (all LLM calls go through here)
  vector_store.py             - ChromaDB wrapper (local vector search)
  persona_bot_safe.py         - Main bot with persona, safety rules, learning cards
  persona_bot.py              - Simpler bot without safety layer
  query_bot.py                - Basic RAG Q&A bot
  learning_card_generator.py  - Generates follow-up suggestions and portfolio examples
  portfolio_images.py         - Matches portfolio images to responses
  voice_generator.py          - ElevenLabs text-to-speech (optional)
  preprocessing/
    transcript_cleaner.py     - Removes timestamps, speaker labels
    concept_extractor.py      - Extracts concepts from text using Claude
    affinity_mapper.py        - Clusters related concepts using Claude
    pipeline.py               - Orchestrates full preprocessing workflow

app/
  streamlit_app_redesign.py   - Main UI (UW-branded, production version)
  streamlit_app.py            - Original multi-tab UI
  streamlit_app_simple.py     - Simplified version
  streamlit_app_v2.py         - Alternative version

scripts/
  ingest_to_chromadb.py       - Index lecture files into ChromaDB
  generate_affinity_map.py    - Generate concept clusters from lectures
  preprocess_lectures.sh      - Batch preprocessing script

data/
  canvas_extracted_512/       - Lecture content (text files)
  affinity_map.json           - Concept clusters
  teaching_concepts.json      - Teaching concept taxonomy
  portfolio_image_metadata.json
  portfolio_images/           - Project screenshots
  chromadb/                   - Vector database (auto-generated, gitignored)
```

## How It Works

### 1. Preprocessing (one-time)
- Clean raw transcripts (remove timestamps, speaker labels)
- Segment into meaningful chunks
- Extract concepts using Claude
- Build affinity map of concept relationships

### 2. Ingestion (one-time)
- Index text segments into ChromaDB
- ChromaDB generates embeddings locally using sentence-transformers
- Data persists to `data/chromadb/`

### 3. Query Processing (runtime)
- User asks a question
- ChromaDB retrieves the most relevant lecture segments via semantic search
- Affinity map identifies related concept clusters
- Claude generates a persona-based response using the retrieved context
- Learning cards suggest follow-up topics and portfolio examples

## Customization

### Change the persona
Edit `src/persona_bot_safe.py` - update `PROFESSIONAL_CONTEXT` and the prompt in `_build_persona_prompt()`.

### Change concept categories
Edit `src/preprocessing/concept_extractor.py`:
```python
self.categories = [
    "Your Category 1",
    "Your Category 2",
]
```

### Use a different model
Pass `model_id` when constructing the bot, or change `DEFAULT_MODEL` in `src/llm_client.py`.

### Enable voice
Set an `ELEVENLABS_API_KEY` in `.streamlit/secrets.toml`. Voice toggle appears in the sidebar.

## Documentation

- [ARCHITECTURE.md](ARCHITECTURE.md) - Detailed system design
- [QUICKSTART.md](QUICKSTART.md) - Step-by-step setup guide
- [PREPROCESSING_GUIDE.md](PREPROCESSING_GUIDE.md) - Transcript preprocessing
- [PERSONA_GUIDE.md](PERSONA_GUIDE.md) - Persona configuration

## License

MIT License - See LICENSE file for details
