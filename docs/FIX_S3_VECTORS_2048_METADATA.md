# Fix: S3 Vectors "Filterable metadata must have at most 2048 bytes"

## Root Cause

Bedrock stores chunk text in `AMAZON_BEDROCK_TEXT` and metadata in `AMAZON_BEDROCK_METADATA`. **By default these are filterable**, and filterable metadata has a 2 KB limit per vector. Chunks of ~1200 characters exceed this when encoded as UTF-8.

Shortening S3 keys or chunk content does not fix this—the limit applies to Bedrock-generated metadata, not our object keys.

## Solution: Non-Filterable Metadata Keys

The S3 vector index must be created with `AMAZON_BEDROCK_TEXT` and `AMAZON_BEDROCK_METADATA` as **non-filterable** metadata keys. Non-filterable metadata can store up to 40 KB per vector.

**Important:** This configuration cannot be changed after the index is created. You must create a new index.

---

## Steps to Fix

### 1. Create a new vector index with correct metadata config

```bash
aws s3vectors create-index \
  --vector-bucket-name "perfectpixels-vectors" \
  --index-name "bedrock-kb-index-v2" \
  --data-type "float32" \
  --dimension 1024 \
  --distance-metric "cosine" \
  --metadata-configuration '{"nonFilterableMetadataKeys":["AMAZON_BEDROCK_TEXT","AMAZON_BEDROCK_METADATA"]}'
```

(Titan Embeddings V2 uses 1024 dimensions; cosine distance matches typical Bedrock config.)

### 2. Create a new Knowledge Base (vector store cannot be changed)

**You cannot change the vector store of an existing KB.** Create a new knowledge base:

1. Go to **Amazon Bedrock** → **Knowledge bases** → **Create knowledge base**
2. **Step 1:** Name it (e.g. `perfectpixels-kb-v3`)
3. **Step 2:** Add S3 data source: bucket `perfectpixels-kb-docs`, prefix `kb-clean/v1/`
4. **Step 3 (Configure data storage and processing):**
   - **Embeddings model:** Click "Select model" → choose **Titan Embeddings V2** (or Amazon Titan Embeddings G1 - Text)
   - **Vector store:** Select **"Use an existing vector store"**
   - **Choose vector bucket ARN:** paste  
     `arn:aws:s3vectors:us-east-1:582234715800:bucket/perfectpixels-vectors`
   - **Choose vector index ARN:** paste  
     `arn:aws:s3vectors:us-east-1:582234715800:bucket/perfectpixels-vectors/index/bedrock-kb-index-v2`
   - (Use **Browse S3** if the console offers it to pick from your buckets/indexes)
5. **Step 4:** Review and create
6. After creation, go to **Data sources** → **Sync**
7. Update `BEDROCK_KNOWLEDGE_BASE_ID` in your app (`.env`, Railway, etc.) with the new KB ID

### 3. (Optional) Delete old resources after verifying

Once sync completes with 0 failures:

- Delete the old KB `SSIRB24COT` if no longer needed (new KB: `HHYCUJH32J`)
- Delete the old index to avoid storage costs:

```bash
aws s3vectors delete-index \
  --vector-bucket-name "perfectpixels-vectors" \
  --index-name "bedrock-kb-index"
```

---

## References

- [Bedrock KB setup: S3 Vectors](https://docs.aws.amazon.com/bedrock/latest/userguide/knowledge-base-setup.html) — "Expand the Additional settings and provide any non-filterable metadata... add `AMAZON_BEDROCK_TEXT` and `AMAZON_BEDROCK_METADATA` as keys"
- [S3 Vectors metadata limits](https://docs.aws.amazon.com/AmazonS3/latest/userguide/s3-vectors-limitations.html) — Filterable: 2 KB; non-filterable: up to 40 KB total
- [AWS re:Post: nonFilterableMetadataKeys](https://repost.aws/questions/QU1CqM9oRpQNmZJYinNFh8ww/using-string-list-metadata-with-s3-vectors-bedrock-knowledge-bases)
