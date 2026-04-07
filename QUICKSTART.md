# Quick Start Guide

Get the Lecture Bot running on your computer in 5 minutes.

## Prerequisites

- **Python 3.11+** - check with `python --version`
- **Anthropic API key** - get one at [console.anthropic.com](https://console.anthropic.com/)

## Setup

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

This installs:
- `streamlit` - web interface
- `anthropic` - Claude API client
- `chromadb` - local vector database (includes embedding model)
- `elevenlabs` - voice output (optional)

On first run, ChromaDB will download its embedding model (~80MB). This only happens once.

### 2. Configure your API key

```bash
cp .streamlit/secrets.toml.example .streamlit/secrets.toml
```

Edit `.streamlit/secrets.toml` and replace the placeholder with your actual key:

```toml
ANTHROPIC_API_KEY = "sk-ant-your-key-here"
```

This file is gitignored and will not be committed.

### 3. Index the lecture data

```bash
python scripts/ingest_to_chromadb.py
```

This reads the lecture text files from `data/` and indexes them into a local ChromaDB vector database. It takes a few seconds and only needs to be done once (or when you add new lectures).

### 4. Start the app

```bash
streamlit run app/streamlit_app_redesign.py
```

Open http://localhost:8501 in your browser. Start asking questions!

## Example Questions to Try

- "What is user research and why does it matter?"
- "How do you approach design systems?"
- "Explain the difference between UX and UI"
- "What was your experience at Amazon?"
- "Give me feedback on my assignment about information architecture"

## Adding Your Own Lectures

1. Place your `.txt` transcript files in a directory:
   ```bash
   mkdir data/my_lectures
   # copy your .txt files there
   ```

2. Index them:
   ```bash
   python scripts/ingest_to_chromadb.py data/my_lectures/
   ```

3. Restart the app. The new content is now searchable.

## Optional: Generate an Affinity Map

The affinity map creates concept clusters that improve retrieval quality. To generate one from your lectures:

```bash
python scripts/generate_affinity_map.py
```

This calls Claude to analyze your lectures and creates `data/affinity_map.json`. The bot will automatically use it if present.

## Optional: Enable Voice

1. Get an API key from [ElevenLabs](https://elevenlabs.io/)
2. Add it to `.streamlit/secrets.toml`:
   ```toml
   ELEVENLABS_API_KEY = "your-elevenlabs-key"
   ```
3. Toggle voice on in the app sidebar

## Troubleshooting

**"ANTHROPIC_API_KEY not found"**
- Check that `.streamlit/secrets.toml` exists and has the correct key
- Or set it as an environment variable: `export ANTHROPIC_API_KEY=sk-ant-...`

**"No documents in store" or empty responses**
- Run `python scripts/ingest_to_chromadb.py` to index the lecture data
- Check that `data/canvas_extracted_512/` or `data/canvas_extracted/` has `.txt` files

**ChromaDB download stalls**
- On first run, ChromaDB downloads an ~80MB embedding model. If this fails, check your internet connection and retry.

**Port 8501 already in use**
- Another Streamlit app is running. Stop it or use: `streamlit run app/streamlit_app_redesign.py --server.port 8502`

## Cost

The only cost is Anthropic API usage:
- ~$0.03 per question (using Claude Sonnet)
- $0/month when nobody is using it
- A class of 20-30 students typically costs $10-30/month during active use
