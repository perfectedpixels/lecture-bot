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
    load_dotenv()
except ImportError:
    pass

from scripts.ingest_transcripts import (
    scrub_transcript,
    detect_concepts,
    chunk_text,
    get_existing_lecture_names,
    convert_rtf,
    S3_BUCKET,
    S3_PREFIX,
    OUTPUT_DIR,
)

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
    with st.spinner("Checking existing lectures..."):
        st.session_state.existing_names = get_existing_lecture_names(
            S3_BUCKET, S3_PREFIX
        )

existing = st.session_state.existing_names

st.sidebar.markdown(f"**{len(existing)}** lectures already in KB")
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

        # Check duplicate
        is_dupe = name in existing

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
        s3 = boto3.client("s3")
        total_uploaded = 0

        progress = st.progress(0, text="Uploading...")
        for idx, item in enumerate(to_push):
            for i, chunk in enumerate(item["chunks"]):
                content_hash = hashlib.md5(chunk.encode()).hexdigest()[:12]
                chunk_filename = (
                    f"lecture-{item['stem']}-part-{i:04d}-{content_hash}.txt"
                )
                header = (
                    f"[Lecture: {item['stem'].replace('-', ' ').replace('_', ' ').title()}]\n"
                    f"[Concepts: {', '.join(item['concepts'])}]\n"
                    f"[Type: lecture]\n\n"
                )
                chunk_path = out / chunk_filename
                chunk_path.write_text(header + chunk, encoding="utf-8")

                # Upload to S3
                s3.upload_file(
                    str(chunk_path),
                    S3_BUCKET,
                    f"{S3_PREFIX}{chunk_filename}",
                )
                total_uploaded += 1

            progress.progress(
                (idx + 1) / len(to_push),
                text=f"Uploaded {item['filename']}...",
            )

        progress.progress(1.0, text="Done!")
        st.session_state.uploaded_count += total_uploaded
        st.success(
            f"✅ Pushed {total_uploaded} chunks from {len(to_push)} file(s) to S3.\n\n"
            f"**Next step:** Sync the Bedrock KB in the "
            f"[AWS console](https://us-east-1.console.aws.amazon.com/bedrock/home?region=us-east-1#/knowledge-bases)."
        )
        # Update existing names so re-uploads show as dupes
        for item in to_push:
            st.session_state.existing_names.add(item["stem"])

elif st.session_state.uploaded_count:
    st.info(
        f"✅ {st.session_state.uploaded_count} chunks uploaded this session. "
        "Upload more files or sync the Bedrock KB."
    )
