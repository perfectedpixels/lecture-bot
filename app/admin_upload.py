"""
Admin transcript upload interface.

Run:  streamlit run app/admin_upload.py

Upload .txt or .rtf lecture transcripts, preview the scrubbed
output, then push to S3 with one click.
"""

import streamlit as st
import sys
import os
import re
import hashlib
import boto3
from pathlib import Path

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "scripts"))

try:
    from dotenv import load_dotenv
    load_dotenv(override=True)  # override ~/.aws with .env values
except ImportError:
    pass

# Ensure boto3 uses .env credentials, not ~/.aws/credentials
_aws_kwargs = {}
if os.environ.get("AWS_ACCESS_KEY_ID") and os.environ.get("AWS_SECRET_ACCESS_KEY"):
    _aws_kwargs = {
        "aws_access_key_id": os.environ["AWS_ACCESS_KEY_ID"],
        "aws_secret_access_key": os.environ["AWS_SECRET_ACCESS_KEY"],
        "region_name": os.environ.get("AWS_REGION", "us-east-1"),
    }


def _s3_client():
    kwargs = dict(_aws_kwargs)
    kwargs.setdefault("region_name", os.environ.get("AWS_REGION", "us-east-1"))
    return boto3.client("s3", **kwargs)


def _agent_client():
    kwargs = dict(_aws_kwargs)
    kwargs.setdefault("region_name", os.environ.get("AWS_REGION", "us-east-1"))
    return boto3.client("bedrock-agent", **kwargs)

from scripts.ingest_transcripts import (
    scrub_transcript,
    detect_concepts,
    chunk_text,
    get_existing_doc_names,
    normalize_doc_name,
    convert_rtf,
    S3_BUCKET,
    S3_PREFIX,
    OUTPUT_DIR,
)
from kb_metadata import write_sidecar, upload_chunk_with_sidecar

KB_ID = os.environ.get("BEDROCK_KNOWLEDGE_BASE_ID", "HHYCUJH32J")
DATA_SOURCE_ID = os.environ.get("BEDROCK_DATA_SOURCE_ID", "B3BHIN3RF8")

st.set_page_config(page_title="Lecture Upload", page_icon="📤", layout="wide")

st.title("📤 Transcript Upload")
st.caption("Upload lecture transcripts → scrub → chunk → push to Knowledge Base")

# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------
if "existing_names" not in st.session_state:
    st.session_state.existing_names = None
if "preview_data" not in st.session_state:
    st.session_state.preview_data = []  # list of dicts per file
if "uploaded_count" not in st.session_state:
    st.session_state.uploaded_count = 0

# ---------------------------------------------------------------------------
# Load existing lecture names (once)
# ---------------------------------------------------------------------------
if st.session_state.existing_names is None:
    with st.spinner("Reading every document already in the KB..."):
        names, ok = get_existing_doc_names(S3_BUCKET, S3_PREFIX)
        st.session_state.existing_names = names
        st.session_state.existing_ok = ok

existing = st.session_state.existing_names

if not st.session_state.get("existing_ok", True):
    # An empty set from a failed listing would look identical to an empty KB
    # and wave every upload through as new. Refuse rather than risk duplicates.
    st.error(
        "Could not list the knowledge base, so duplicates cannot be detected. "
        "Fix credentials before uploading — pushing now risks a second copy of "
        "material that is already indexed."
    )
    st.stop()

st.sidebar.markdown(f"**{len(existing)}** documents already in KB")
doc_type = st.sidebar.selectbox(
    "Content type",
    ["lecture", "framework", "case-study", "assignment"],
    help="Tags the chunks. 'lecture' is course material; 'framework' is "
         "professional/reference material.",
)
st.sidebar.markdown("---")
st.sidebar.markdown("### How it works")
st.sidebar.markdown("""
1. Upload `.txt` or `.rtf` files
2. Preview scrubbed text & detected concepts
3. Click **Push to Knowledge Base**
4. Sync Bedrock KB in the AWS console
""")

# ---------------------------------------------------------------------------
# File upload
# ---------------------------------------------------------------------------
uploaded_files = st.file_uploader(
    "Drop lecture transcripts here",
    type=["txt", "rtf"],
    accept_multiple_files=True,
    help="Raw .txt or .rtf lecture transcripts",
)

if uploaded_files:
    preview_data = []

    for uf in uploaded_files:
        name = Path(uf.name).stem
        raw_bytes = uf.read()

        # Decode
        if uf.name.lower().endswith(".rtf"):
            try:
                from striprtf.striprtf import rtf_to_text
                raw_text = rtf_to_text(raw_bytes.decode("utf-8", errors="replace"))
            except ImportError:
                st.error("striprtf not installed — cannot process RTF files")
                continue
        else:
            raw_text = raw_bytes.decode("utf-8", errors="replace")

        # Duplicate check spans every naming convention in the KB, not just
        # files this tool happened to upload.
        is_dupe = normalize_doc_name(name) in existing

        # Scrub
        scrubbed = scrub_transcript(raw_text)
        word_count = len(scrubbed.split())
        concepts = detect_concepts(scrubbed)
        chunks = chunk_text(scrubbed, max_tokens=400, overlap=50)

        preview_data.append({
            "filename": uf.name,
            "stem": name,
            "raw_text": raw_text,
            "scrubbed": scrubbed,
            "word_count": word_count,
            "concepts": concepts,
            "chunks": chunks,
            "is_dupe": is_dupe,
            "doc_type": doc_type,
        })

    st.session_state.preview_data = preview_data

    # --- Preview each file ---
    for i, item in enumerate(preview_data):
        dupe_tag = " ⚠️ DUPLICATE" if item["is_dupe"] else ""
        with st.expander(
            f"{'⚠️' if item['is_dupe'] else '✅'} {item['filename']} — "
            f"{item['word_count']} words, {len(item['chunks'])} chunks, "
            f"concepts: {', '.join(item['concepts'])}{dupe_tag}",
            expanded=not item["is_dupe"],
        ):
            col1, col2 = st.columns(2)
            with col1:
                st.markdown("**Raw (first 500 chars)**")
                st.text(item["raw_text"][:500])
            with col2:
                st.markdown("**Scrubbed (first 500 chars)**")
                st.text(item["scrubbed"][:500])

            if item["is_dupe"]:
                st.warning(
                    f"'{item['stem']}' already exists in the KB. "
                    "It will be skipped unless you check the box below."
                )
                item["force"] = st.checkbox(
                    f"Re-ingest '{item['stem']}' anyway",
                    key=f"force_{i}",
                )
            else:
                item["force"] = False

    # --- Push button ---
    to_push = [
        p for p in preview_data
        if not p["is_dupe"] or p.get("force")
    ]

    st.markdown("---")
    col_a, col_b = st.columns([3, 1])
    with col_a:
        st.markdown(
            f"**{len(to_push)}** file(s) ready to push "
            f"({sum(len(p['chunks']) for p in to_push)} chunks total)"
        )
    with col_b:
        push = st.button(
            "🚀 Push to Knowledge Base",
            type="primary",
            disabled=len(to_push) == 0,
            use_container_width=True,
        )

    if push:
        out = Path(OUTPUT_DIR)
        out.mkdir(parents=True, exist_ok=True)
        s3 = _s3_client()
        total_uploaded = 0

        progress = st.progress(0, text="Uploading...")
        for idx, item in enumerate(to_push):
            for i, chunk in enumerate(item["chunks"]):
                content_hash = hashlib.md5(chunk.encode()).hexdigest()[:12]
                chunk_filename = (
                    f"{item['doc_type']}-{item['stem']}-part-{i:04d}-{content_hash}.txt"
                )
                header = (
                    f"[{item['doc_type'].title()}: "
                    f"{item['stem'].replace('-', ' ').replace('_', ' ').title()}]\n"
                    f"[Concepts: {', '.join(item['concepts'])}]\n"
                    f"[Type: {item['doc_type']}]\n\n"
                )
                chunk_path = out / chunk_filename
                chunk_path.write_text(header + chunk, encoding="utf-8")

                # Write the Bedrock metadata sidecar, then upload BOTH. The
                # previous version called s3.upload_file() on the chunk alone,
                # so everything this tool ever pushed arrived untagged -- no
                # layer, no doc_type, no concepts -- and was invisible to
                # metadata-filtered retrieval.
                write_sidecar(
                    chunk_path,
                    layer="reference",
                    doc_type=item["doc_type"],
                    concepts=item["concepts"],
                )
                upload_chunk_with_sidecar(
                    s3, chunk_path, S3_BUCKET, f"{S3_PREFIX}{chunk_filename}"
                )
                total_uploaded += 1

            progress.progress(
                (idx + 1) / len(to_push),
                text=f"Uploaded {item['filename']}...",
            )

        progress.progress(1.0, text="Done!")
        st.session_state.uploaded_count += total_uploaded
        st.session_state.needs_sync = True
        st.success(
            f"✅ Pushed {total_uploaded} chunks from {len(to_push)} file(s) to S3."
        )

# ---------------------------------------------------------------------------
# Indexing
#
# Uploading to S3 does NOT make content searchable -- Bedrock only sees it after
# an ingestion job runs. This used to be a "now go to the AWS console" note, and
# the job history shows the consequence: nothing was indexed between 2026-04-23
# and 2026-08-19 even though chunks had been uploaded. Making it a button in the
# same screen removes the step that gets forgotten.
# ---------------------------------------------------------------------------
if st.session_state.get("needs_sync"):
    st.warning(
        "Uploaded chunks are in S3 but **not yet searchable**. "
        "Bedrock indexes them only when an ingestion job runs."
    )
    if st.button("🔄 Index now (run Bedrock ingestion)", type="primary"):
        try:
            job = _agent_client().start_ingestion_job(
                knowledgeBaseId=KB_ID, dataSourceId=DATA_SOURCE_ID
            )
            jid = job["ingestionJob"]["ingestionJobId"]
            st.session_state.needs_sync = False
            st.session_state.last_job = jid
            st.success(
                f"Ingestion job `{jid}` started. It runs for a few minutes; "
                "use the button below to check on it."
            )
        except Exception as e:
            st.error(f"Could not start the ingestion job: {e}")

if st.session_state.get("last_job"):
    if st.button("Check indexing status"):
        try:
            r = _agent_client().get_ingestion_job(
                knowledgeBaseId=KB_ID,
                dataSourceId=DATA_SOURCE_ID,
                ingestionJobId=st.session_state.last_job,
            )["ingestionJob"]
            stats = r.get("statistics", {})
            st.info(
                f"**{r['status']}** — scanned {stats.get('numberOfDocumentsScanned', 0)}, "
                f"newly indexed {stats.get('numberOfNewDocumentsIndexed', 0)}, "
                f"failed {stats.get('numberOfDocumentsFailed', 0)}"
            )
            if r["status"] == "FAILED":
                st.error(r.get("failureReasons"))
        except Exception as e:
            st.error(f"Could not read job status: {e}")
        # Update existing names so re-uploads show as dupes
        for item in to_push:
            st.session_state.existing_names.add(normalize_doc_name(item["stem"]))

elif st.session_state.uploaded_count:
    st.info(
        f"✅ {st.session_state.uploaded_count} chunks uploaded this session. "
        "Upload more files or sync the Bedrock KB."
    )
