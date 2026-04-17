# Adding New Transcripts to HHYCUJH32J

Procedure to parse, chunk, and add new lecture transcripts to the shared Knowledge Base (HHYCUJH32J). One pipeline, one sync — lecture-bot and ppmg both use the same KB.

---

## Prerequisites

- AWS CLI configured (profile with access to `perfectpixels-kb-docs` bucket)
- Raw transcript as `.txt` or `.md` (WEBVTT converted to plain text, or markdown)

---

## Step 1: Prepare the transcript

**If you have WEBVTT or messy transcript:**

- Remove timestamps (`[00:01:23]`, `00:01:23.000`)
- Remove speaker labels (`Jason Levine:`, `Speaker 1:`)
- Save as plain `.txt` or `.md`

You can use the Streamlit app **Preprocess** tab, or run the preprocessing pipeline locally:

```bash
cd lecture-bot
python -m src.preprocessing.pipeline path/to/raw_transcript.txt output_dir/
```

Or clean manually — the chunking script will normalize line endings.

---

## Step 2: Upload raw file to S3

Upload **outside** `kb-clean/` (the chunker reads from everywhere except `kb-clean/` and `rechunked/`):

```bash
aws s3 cp your-lecture.txt s3://perfectpixels-kb-docs/lectures/ \
  --profile personal
```

Or use a subfolder:

```bash
aws s3 cp 2026-03-15-ux-research-qa.txt s3://perfectpixels-kb-docs/lectures/
```

---

## Step 3: Run the chunking pipeline

This script reads all `.txt` and `.md` files from the bucket, chunks them (1200 chars, 200 overlap), and writes to `kb-clean/v1/`. It **overwrites** the entire `kb-clean/v1/` prefix each run.

```bash
cd lecture-bot
python scripts/build_kb_clean_prefix.py \
  --bucket perfectpixels-kb-docs \
  --target-prefix kb-clean/v1 \
  --profile personal
```

**Options:**

| Flag | Default | Description |
|------|---------|-------------|
| `--bucket` | `perfectpixels-kb-docs` | S3 bucket |
| `--target-prefix` | `kb-clean/v1` | Output prefix (KB data source) |
| `--chunk-size` | 1200 | Characters per chunk |
| `--overlap` | 200 | Overlap between chunks |
| `--profile` | `personal` | AWS profile |

**Output:** Chunks in `s3://perfectpixels-kb-docs/kb-clean/v1/` with format:

```
Source: lectures/your-lecture.txt

{chunk text}
```

---

## Step 4: Sync the Knowledge Base

1. Open [AWS Bedrock Console → Knowledge Bases](https://us-east-1.console.aws.amazon.com/bedrock/home?region=us-east-1#/knowledge-bases)
2. Select **HHYCUJH32J**
3. Click **Sync** (data source should point to `s3://perfectpixels-kb-docs/kb-clean/v1/`)
4. Wait for sync to complete (typically 5–15 minutes)

---

## Step 5: Verify

Test the chatbot (Streamlit or ppmg portfolio) with prompts related to the new content.

---

## Quick reference

```bash
# 1. Upload
aws s3 cp new-lecture.txt s3://perfectpixels-kb-docs/lectures/ --profile personal

# 2. Chunk (processes ALL docs in bucket)
python scripts/build_kb_clean_prefix.py --bucket perfectpixels-kb-docs --profile personal

# 3. Sync in Bedrock Console
```

---

## Troubleshooting: "Filterable metadata must have at most 2048 bytes"

This error is caused by the **S3 vector index configuration**, not the chunk files. The index must have `AMAZON_BEDROCK_TEXT` and `AMAZON_BEDROCK_METADATA` set as non-filterable metadata keys when created.

**Fix:** Create a new vector index with the correct config and point the KB to it. See **`docs/FIX_S3_VECTORS_2048_METADATA.md`** for full steps.

## Notes

- **Keyword extraction:** The chunker does not add keywords. Query expansion and reranking in `persona_bot_fast.py` handle domain terms at query time.
- **Full preprocessing:** For concept extraction, affinity maps, and metadata, use the Streamlit **Preprocess** tab or `python -m src.preprocessing.pipeline`. That outputs JSON for a different KB setup; for HHYCUJH32J, the simple chunk pipeline above is sufficient.
- **Incremental adds:** Each run of `build_kb_clean_prefix.py` processes the entire bucket. Add new files to S3, then re-run the script and sync.
