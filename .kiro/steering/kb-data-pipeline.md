---
inclusion: auto
---

# KB Data Pipeline & S3 Vectors Metadata Fix

## The Problem

When syncing Bedrock KB `HHYCUJH32J`, S3 Vectors rejects records with:
`Filterable metadata must have at most 2048 bytes`

- March 6 sync: 2508 files, 0 failures (clean)
- March 16 sync: 3000 files, 349 failures — the ~492 new files are the ones failing

## KB Configuration

- **KB ID**: `HHYCUJH32J` (shared ppmg/lecture-bot KB)
- **Data source**: `perfectpixels-docs` / `NXVTBANBLQ`
- **Bucket**: `s3://perfectpixels-kb-docs/kb-clean/v1/`
- **Account**: `582234715800` (personal)
- **Chunking strategy**: Default
- **Parsing strategy**: Default
- **Vector store**: S3 Vectors (`perfectpixels-vectors`)

## Data Pipeline (3 stages)

### Stage 1: Raw Source Materials
Local directories with original unprocessed content:
- `data/raw_transcripts/` — lecture transcript .txt files
- `data/assignments_raw/` — COMMLD-515 assignment HTML files
- `data/assignments_raw_512/` — COMMLD-512 assignment HTML files
- `data/grading/` — grading handbook .txt
- `data/new_lectures/` — new lecture .txt files to process

### Stage 2: Cleaned & Stripped
Processed locally, removing timestamps, speaker labels, HTML tags:
- `data/processed_transcripts/` — cleaned transcript chunks
- `data/assignments_chunked/` — cleaned assignment chunks with inline metadata headers
- `data/grading_chunked/` — cleaned grading rubric chunks with inline metadata headers
- `data/lectures_chunked/` — cleaned lecture chunks with inline metadata headers

### Stage 3: Uploaded to S3 (`kb-clean/v1/`)
Four scripts upload to `s3://perfectpixels-kb-docs/kb-clean/v1/`:

| Script | What it uploads | S3 user metadata? |
|--------|----------------|-------------------|
| `scripts/build_kb_clean_prefix.py` | Re-chunks ALL source .txt/.md from bucket into `kb-clean/v1/` | No |
| `scripts/process_assignments.py` | Assignment chunks from `data/assignments_chunked/` | No |
| `scripts/process_grading.py` | Grading chunks from `data/grading_chunked/` | No |
| `scripts/process_lectures.py` | Lecture chunks from `data/lectures_chunked/` | No |

### Canvas API Sync (live assignment pull)
`scripts/canvas_sync.py` connects to the UW Canvas API to pull live assignment data, detect concept overlap with lecture material, and output:
- `data/canvas_assignments/<course>/` — raw JSON per assignment (id, description, concepts, alignment)
- `data/assignments_chunked/` — chunked .txt files with inline metadata headers (same format as `process_assignments.py`)
- `data/canvas_lecture_alignment.json` — full alignment report mapping assignments → teaching concepts

Requires `CANVAS_API_TOKEN`, `CANVAS_BASE_URL`, and `CANVAS_COURSE_IDS` in `.env`.

### Old scripts (target decommissioned bucket — DO NOT USE for current KB)
| Script | Target bucket | S3 user metadata? |
|--------|--------------|-------------------|
| `scripts/clean_rebuild.py` | `lecture-transcripts-427791004700` | YES — sets topics, concepts, companies, etc. |
| `scripts/add_metadata_to_s3.py` | `lecture-transcripts-427791004700` | YES — re-uploads with metadata |

## What Was Changed (March 17, 2026)

Added a `_truncate_metadata()` helper to `clean_rebuild.py` and `add_metadata_to_s3.py` that caps
S3 user metadata to 1500 bytes. However, these scripts target the OLD decommissioned bucket
(`lecture-transcripts-427791004700`), NOT the current `perfectpixels-kb-docs` bucket.
**These changes do not affect the current KB.**

## Root Cause (confirmed)

Bedrock stores chunk text in `AMAZON_BEDROCK_TEXT` and metadata in `AMAZON_BEDROCK_METADATA`. **By default these are filterable**, and S3 Vectors limits filterable metadata to 2048 bytes per vector. Chunks of ~1200 chars exceed this.

Shortening S3 keys or chunk content does **not** fix this—the limit applies to Bedrock-generated metadata.

## Fix: S3 Vector Index Configuration

The vector index must be created with `AMAZON_BEDROCK_TEXT` and `AMAZON_BEDROCK_METADATA` as **non-filterable** metadata keys. This cannot be changed after creation—**create a new index**.

See **`docs/FIX_S3_VECTORS_2048_METADATA.md`** for full steps (create new index, update KB, sync).

## Chunk Script Changes (partial mitigation only)

Shortened `target_key()` and Source line in `build_kb_clean_prefix.py`—helps with key length but does not resolve the filterable-metadata limit. The index config fix above is required.
