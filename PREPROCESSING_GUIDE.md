# Lecture Preprocessing Guide

This guide explains how to preprocess your lecture transcripts for the AI chatbot.

## What the Pipeline Does

1. **Cleans Transcripts**
   - Removes timestamps (00:01:23, [00:01:23], etc.)
   - Removes speaker labels ("Jason Levine:", etc.)
   - Preserves semantic meaning

2. **Segments Content**
   - Breaks lectures into meaningful chunks (200-1000 chars)
   - Keeps related content together
   - Optimized for vector search

3. **Extracts Concepts**
   - Uses Claude to identify key concepts in each segment
   - Tags with categories (AI, Design, UX, etc.)
   - Assigns confidence scores

4. **Creates Affinity Map**
   - Builds co-occurrence matrix (which concepts appear together)
   - Creates semantic clusters of related concepts
   - Enables intelligent context retrieval

## Quick Start

### Process a Single Lecture

```bash
python3 src/preprocessing/pipeline.py \
  raw_transcripts/lecture1.txt \
  processed_lectures/
```

### Process Multiple Lectures

```bash
# Using the helper script
chmod +x scripts/preprocess_lectures.sh
./scripts/preprocess_lectures.sh raw_transcripts/ processed_lectures/

# Or directly
python3 src/preprocessing/pipeline.py \
  raw_transcripts/ \
  processed_lectures/
```

## Input Format

Your transcript files should be `.txt` files. They can include:

- Timestamps (will be removed)
- Speaker labels (will be removed)
- Optional metadata header:
  ```
  Lecture: Introduction to AI
  Date: February 10, 2026
  Topic: Machine Learning Basics
  ```

Example raw transcript:
```
Lecture: AI and Design
Date: Feb 10, 2026

00:01:23 Jason Levine: Today we're discussing AI in design.
00:01:45 Jason Levine: The key is understanding user needs.

00:02:10 When we think about UX...
```

## Output Structure

```
processed_lectures/
├── master_index.json              # Overview of all lectures
├── affinity_map.json              # Concept clusters and relationships
├── lecture1_segment_1.json        # Individual segments
├── lecture1_segment_2.json
├── lecture1_summary.json          # Lecture summary
├── lecture2_segment_1.json
└── ...
```

### Segment File Format

Each segment file contains:
```json
{
  "text": "cleaned segment text...",
  "metadata": {
    "primary_category": "AI/Machine Learning",
    "concepts": "neural networks, deep learning, backpropagation",
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

### Affinity Map Format

```json
{
  "clusters": [
    {
      "cluster_id": "ml_fundamentals",
      "concepts": ["neural networks", "deep learning", "supervised learning"],
      "central_concept": "neural networks",
      "categories": ["AI/Machine Learning", "Theory/Concepts"],
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

## Customization

### Change Speaker Name

```bash
python3 src/preprocessing/pipeline.py \
  input.txt output/ \
  --speaker "Your Name"
```

### Skip Affinity Map

```bash
python3 src/preprocessing/pipeline.py \
  input/ output/ \
  --no-affinity
```

### Adjust Concept Categories

Edit `src/preprocessing/concept_extractor.py`:
```python
self.categories = [
    "Your Category 1",
    "Your Category 2",
    # ...
]
```

## Index for Search

After preprocessing, index the processed segments into ChromaDB:

```bash
python scripts/ingest_to_chromadb.py processed_lectures/
```

## Troubleshooting

**"Error extracting concepts"**
- Check that `ANTHROPIC_API_KEY` is set (env var or `.streamlit/secrets.toml`)

**"No .txt files found"**
- Check input directory path
- Ensure files have `.txt` extension

**Segments too small/large**
- Adjust in `transcript_cleaner.py`:
  ```python
  min_segment_length = 200  # Minimum chars
  max_segment_size = 1000   # Maximum chars
  ```

## Next Steps

1. Review processed segments in output directory
2. Check `master_index.json` for overview
3. Explore `affinity_map.json` to see concept clusters
4. Run `python scripts/ingest_to_chromadb.py` to make content searchable
5. Restart the chatbot to use the new data
