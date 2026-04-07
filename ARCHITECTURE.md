# Architecture: Lecture Bot

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER INTERFACE                          │
│                    (Streamlit Web App)                           │
│  - Chat with persona         - Learning cards                   │
│  - Generate reports          - Portfolio examples               │
│  - Analyze assignments       - Voice output (optional)          │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                      PERSONA BOT LAYER                          │
│  - Safety checks                                                │
│  - Concept-aware context selection (affinity map)               │
│  - Persona prompt engineering                                   │
│  - Learning card generation                                     │
└──────────┬─────────────────────────────────┬────────────────────┘
           │                                 │
           ▼                                 ▼
┌─────────────────────────┐   ┌──────────────────────────────────┐
│    ANTHROPIC SDK         │   │         CHROMADB                 │
│  (Claude API)            │   │   (Local Vector Database)        │
│  - Answer generation     │   │  - Semantic search               │
│  - Concept extraction    │   │  - Sentence-transformer embeds   │
│  - Affinity clustering   │   │  - Persists to data/chromadb/    │
└─────────────────────────┘   └──────────────────────────────────┘
                                             │
                                             ▼
                               ┌──────────────────────────────────┐
                               │      LOCAL FILESYSTEM             │
                               │  data/canvas_extracted_512/       │
                               │  data/affinity_map.json           │
                               │  data/portfolio_images/           │
                               │  data/teaching_concepts.json      │
                               └──────────────────────────────────┘
```

## Design Principles

**Local-first**: Everything runs on a single machine. No cloud infrastructure, no servers to manage, no accounts to configure beyond a single API key.

**Pay-per-use**: The only external cost is Anthropic API usage (~$0.03/query). No fixed monthly costs. $0 when idle.

**Minimal dependencies**: Two key libraries do the heavy lifting:
- `anthropic` - Claude API calls
- `chromadb` - Embedded vector database (includes its own embedding model)

## Data Flow

### Preprocessing Pipeline (one-time, offline)

```
Raw Transcripts (.txt files)
    │
    ├──► TranscriptCleaner
    │    - Remove timestamps (HH:MM:SS)
    │    - Remove speaker labels
    │    - Semantic segmentation into chunks
    │
    ├──► ConceptExtractor (calls Claude)
    │    - Extract key concepts per segment
    │    - Categorize: AI/ML, Design, UX, etc.
    │    - Assign confidence scores
    │
    └──► AffinityMapper (calls Claude)
         - Build concept co-occurrence matrix
         - Create semantic clusters
         - Calculate affinity scores
         │
         ▼
    Output files (all in data/):
    - Processed segments (JSON per segment)
    - affinity_map.json (concept clusters)
    - master_index.json (overview)
```

### Ingestion (one-time)

```
Text files in data/
    │
    └──► scripts/ingest_to_chromadb.py
         - Reads all .txt files
         - ChromaDB generates embeddings locally
           (sentence-transformers all-MiniLM-L6-v2)
         - Stores in data/chromadb/ (persistent)
```

### Query Flow (runtime, per user question)

```
User Question
    │
    ├──► Safety Check
    │    - Reject personal info requests
    │    - Reject inappropriate content
    │
    ├──► Concept Identification (Claude, ~300 tokens)
    │    - Analyze query against affinity map clusters
    │    - Return relevant concept cluster IDs
    │
    ├──► Vector Search (ChromaDB, local)
    │    - Semantic similarity search
    │    - Return top N matching lecture segments
    │    - No network call - runs in-process
    │
    ├──► Context Assembly
    │    - Combine retrieved segments
    │    - Add relevant concepts from affinity map
    │    - Build persona prompt with safety rules
    │
    ├──► Answer Generation (Claude, ~800 tokens)
    │    - Respond as instructor persona
    │    - Reference specific lectures
    │    - Maintain teaching style
    │
    └──► Learning Cards (Claude, ~800 tokens)
         - Identify related teaching concepts
         - Find matching portfolio examples
         - Generate follow-up suggestions
         │
         ▼
    Response: answer + sources + concepts + learning cards
```

## Key Components

### src/llm_client.py

Thin wrapper around the Anthropic Python SDK. All Claude API calls in the project go through `call_claude()`. This centralizes:
- API key management (env var or Streamlit secrets)
- Default model selection
- Response parsing

### src/vector_store.py

Wrapper around ChromaDB's PersistentClient. Provides:
- `ingest(documents, metadatas, ids)` - add documents
- `query(text, n_results)` - semantic search, returns `[{text, source, metadata, score}]`

ChromaDB runs fully embedded (no server process). It uses the `all-MiniLM-L6-v2` sentence-transformer model for embeddings, which downloads once (~80MB) and runs locally.

### src/persona_bot_safe.py

The main bot used in production. Features:
- Safety guardrails (rejects personal info requests, inappropriate content)
- Professional context injection (instructor background)
- Affinity-map-aware concept identification
- Integration with LearningCardGenerator
- Concise, teaching-focused response style

### src/learning_card_generator.py

Generates contextual follow-up content after each response:
1. **Related Concepts** - from the affinity map (same/related clusters)
2. **Teaching Concepts** - high-level concepts matched via Claude
3. **Portfolio Examples** - relevant project images scored by semantic similarity

## Data Structures

### Affinity Map (`data/affinity_map.json`)

```json
{
  "clusters": [
    {
      "cluster_id": "research_methods",
      "concepts": ["user interviews", "surveys", "usability testing"],
      "central_concept": "User Research",
      "categories": ["User Experience"],
      "segment_count": 15,
      "affinity_score": 8.5,
      "related_clusters": ["personas", "data_analysis"]
    }
  ],
  "concept_relationships": {
    "user interviews": { "surveys": 12, "personas": 8 }
  }
}
```

### ChromaDB Collection

- **Collection name**: `lecture_segments`
- **Embedding model**: `all-MiniLM-L6-v2` (384 dimensions)
- **Distance metric**: cosine
- **Metadata per document**: `source` (filename), `path` (full path)
- **Persistence**: `data/chromadb/`

## Cost Breakdown (per query)

| Step | Model | Input tokens | Output tokens | Cost |
|------|-------|-------------|---------------|------|
| Concept identification | Sonnet | ~800 | ~200 | ~$0.005 |
| Answer generation | Sonnet | ~3,000 | ~500 | ~$0.017 |
| Teaching concepts | Sonnet | ~1,500 | ~300 | ~$0.009 |
| **Total per query** | | | | **~$0.03** |

Vector search (ChromaDB) is free - it runs locally.

## Concept Categories

Default categories used by the concept extractor (customizable):

- AI/Machine Learning
- Design
- User Experience
- Technology
- Biography/Personal
- Frameworks/Methodologies
- Case Studies
- Theory/Concepts
- Tools/Software
- Business/Strategy
