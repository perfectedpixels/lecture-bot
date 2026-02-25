# Architecture: Persona Lecture Bot

## System Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER INTERFACE                          │
│                    (Streamlit Web App)                          │
│  - Chat with persona                                            │
│  - Generate reports                                             │
│  - Analyze assignments                                          │
│  - View concept clusters                                        │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                      PERSONA BOT LAYER                          │
│  - Persona prompt engineering                                   │
│  - Concept-aware context selection                              │
│  - Affinity map integration                                     │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                   AWS BEDROCK KNOWLEDGE BASE                    │
│  - Vector search (Titan Embeddings)                             │
│  - Metadata filtering                                           │
│  - Source attribution                                           │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    OPENSEARCH SERVERLESS                        │
│  - Vector storage                                               │
│  - Semantic search                                              │
└─────────────────────────────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                         S3 BUCKET                               │
│  /lectures/          - Processed text segments                  │
│  /metadata/          - Affinity map, master index               │
└─────────────────────────────────────────────────────────────────┘
```

## Data Flow

### 1. Preprocessing Pipeline (Offline)

```
Raw Transcripts
    │
    ├─► TranscriptCleaner
    │   - Remove timestamps
    │   - Remove speaker labels
    │   - Semantic segmentation
    │
    ├─► ConceptExtractor (Claude)
    │   - Extract key concepts
    │   - Categorize concepts
    │   - Assign confidence scores
    │
    └─► AffinityMapper (Claude)
        - Build co-occurrence matrix
        - Create semantic clusters
        - Calculate affinity scores
        │
        ▼
    Processed Segments + Affinity Map
```

### 2. Query Flow (Runtime)

```
User Question
    │
    ├─► Concept Identification (Claude)
    │   - Analyze query
    │   - Match to concept clusters
    │   - Get relevant concepts
    │
    ├─► Knowledge Base Retrieval
    │   - Vector search
    │   - Metadata filtering (concepts)
    │   - Retrieve top N segments
    │
    ├─► Context Assembly
    │   - Combine retrieved segments
    │   - Add concept context
    │   - Build persona prompt
    │
    └─► Answer Generation (Claude)
        - Apply persona instructions
        - Generate response
        - Include source attribution
        │
        ▼
    Persona-based Answer + Sources + Concepts
```

## Key Components

### 1. Preprocessing Pipeline

**Location:** `src/preprocessing/`

**Components:**
- `transcript_cleaner.py` - Removes noise from transcripts
- `concept_extractor.py` - Extracts and tags concepts using Claude
- `affinity_mapper.py` - Creates concept clusters and relationships
- `pipeline.py` - Orchestrates the full preprocessing workflow

**Input:** Raw lecture transcripts (.txt)
**Output:** 
- Cleaned segments (JSON)
- Affinity map (JSON)
- Master index (JSON)

### 2. Persona Bot

**Location:** `src/persona_bot.py`

**Features:**
- Concept-aware context selection
- Persona prompt engineering
- Affinity map integration
- Assignment analysis
- Report generation

**Key Methods:**
- `query()` - Main Q&A with persona
- `analyze_assignment()` - Provide instructor feedback
- `explain_concept()` - Teach in instructor's style
- `generate_report()` - Create comprehensive reports

### 3. Web Interface

**Location:** `app/streamlit_app.py`

**Features:**
- Chat interface with history
- Report generation
- Assignment analysis
- Concept exploration
- Source browsing

**Configuration:**
- Knowledge Base ID
- Affinity map upload
- Persona settings
- Model selection

### 4. AWS Infrastructure

**Location:** `infrastructure/lib/lecture-bot-stack.ts`

**Resources:**
- S3 bucket (versioned, encrypted)
- Lambda function (transcript processing)
- IAM roles (Bedrock access)
- CloudFormation outputs

## Data Structures

### Processed Segment

```json
{
  "text": "cleaned lecture content...",
  "metadata": {
    "primary_category": "AI/Machine Learning",
    "concepts": "neural networks, deep learning",
    "categories": "AI/Machine Learning, Theory/Concepts",
    "concept_count": "3",
    "lecture": "Introduction to AI",
    "date": "Feb 10, 2026"
  },
  "concepts": [
    {
      "name": "neural networks",
      "category": "AI/Machine Learning",
      "confidence": 0.95
    }
  ]
}
```

### Affinity Map

```json
{
  "clusters": [
    {
      "cluster_id": "ml_fundamentals",
      "concepts": ["neural networks", "deep learning"],
      "central_concept": "neural networks",
      "categories": ["AI/Machine Learning"],
      "segment_count": 15,
      "affinity_score": 8.5
    }
  ],
  "concept_relationships": {
    "neural networks": {
      "deep learning": 12,
      "backpropagation": 8
    }
  }
}
```

## Concept Categories

Default categories (customizable):
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

## Persona Prompt Structure

```
You are {persona_name}, responding to a student's question.

INSTRUCTIONS:
- Respond in first person
- Reference your lectures
- Use your teaching style
- Provide practical examples

CONTEXT:
{retrieved_lecture_segments}

RELEVANT CONCEPTS:
{concepts_from_affinity_map}

QUESTION:
{user_question}
```

## Scalability Considerations

### Current Limits
- ~1000 lectures (OpenSearch Serverless)
- ~10MB per lecture transcript
- ~100 queries/day (cost-optimized)

### Scaling Options
1. **More lectures:** Increase OpenSearch capacity
2. **More queries:** Use caching layer (Redis)
3. **Faster responses:** Use Claude Haiku for concept extraction
4. **Lower costs:** Batch preprocessing, cache affinity maps

## Security

- S3 bucket: Private, encrypted at rest
- IAM roles: Least privilege access
- Bedrock: Regional isolation
- No PII in transcripts (cleaned during preprocessing)

## Monitoring

Key metrics to track:
- Query latency
- Concept match accuracy
- User satisfaction (feedback)
- Cost per query
- Knowledge Base sync time

## Future Enhancements

1. **Real-time transcription** - AWS Transcribe integration
2. **Multi-modal** - Support for lecture videos/slides
3. **Collaborative** - Multiple instructors
4. **Analytics** - Student learning insights
5. **Mobile app** - Native iOS/Android
6. **Voice interface** - Alexa/Google Assistant
