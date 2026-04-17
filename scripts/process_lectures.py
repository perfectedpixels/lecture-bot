"""
Process lecture text files into chunked text for Bedrock KB ingestion.

Usage:
    1. Drop .txt files into data/new_lectures/
    2. Run: python3 scripts/process_lectures.py
    3. Sync the Bedrock KB in the AWS console

The script will chunk, tag, upload to S3, then move processed files
to data/new_lectures/done/ so they don't get re-processed.
"""

import re
import hashlib
import boto3
from pathlib import Path


CONCEPT_KEYWORDS = {
    'personas': ['persona', 'user persona', 'empathy map', 'archetype'],
    'heuristics': ['heuristic', 'nielsen', 'usability heuristic', 'design principle'],
    'usability': ['usability', 'usability test', 'usability study', 'usability script', 'task analysis'],
    'user-research': ['interview', 'survey', 'qualitative', 'quantitative', 'user research', 'field study'],
    'prototyping': ['prototype', 'wireframe', 'mockup', 'paper prototype', 'lo-fi', 'hi-fi'],
    'design-thinking': ['design thinking', 'ideation', 'brainstorm', 'journey map', 'storyboard'],
    'ai-design': ['artificial intelligence', 'machine learning', 'llm', 'generative ai', 'neural network'],
    'branding': ['brand', 'branding', 'identity', 'logo', 'visual identity'],
    'accessibility': ['accessibility', 'wcag', 'screen reader', 'a11y', 'assistive'],
}


def detect_concepts(text: str) -> list:
    text_lower = text.lower()
    found = []
    for concept, keywords in CONCEPT_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            found.append(concept)
    return found if found else ['general']


def chunk_text(text: str, max_tokens: int = 400, overlap: int = 50) -> list:
    words = text.split()
    chunks = []
    start = 0
    while start < len(words):
        end = min(start + max_tokens, len(words))
        chunk = ' '.join(words[start:end])
        if chunk.strip():
            chunks.append(chunk.strip())
        start += max_tokens - overlap
    return chunks


def process_lectures(input_dir: str, output_dir: str) -> list:
    """Process all .txt files in input_dir into tagged chunks."""
    inp = Path(input_dir)
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    txt_files = sorted(inp.glob('*.txt'))
    if not txt_files:
        print(f"No .txt files found in {input_dir}/")
        return []

    all_chunks = []

    for txt_file in txt_files:
        filename = txt_file.stem
        text = txt_file.read_text(encoding='utf-8', errors='replace').strip()

        if len(text.split()) < 20:
            print(f"  Skipping {filename} (too short: {len(text.split())} words)")
            continue

        concepts = detect_concepts(text)
        chunks = chunk_text(text, max_tokens=400, overlap=50)

        print(f"  {filename}: {len(text.split())} words -> {len(chunks)} chunks | concepts: {concepts}")

        for i, chunk in enumerate(chunks):
            content_hash = hashlib.md5(chunk.encode()).hexdigest()[:12]
            chunk_filename = f"lecture-{filename}-part-{i:04d}-{content_hash}.txt"

            header = (
                f"[Lecture: {filename.replace('-', ' ').title()}]\n"
                f"[Concepts: {', '.join(concepts)}]\n"
                f"[Type: lecture]\n\n"
            )
            (out / chunk_filename).write_text(header + chunk, encoding='utf-8')
            all_chunks.append(chunk_filename)

    return all_chunks


def upload_to_s3(output_dir: str, bucket: str, prefix: str) -> int:
    s3 = boto3.client('s3')
    out = Path(output_dir)
    uploaded = 0

    for txt_file in sorted(out.glob('lecture-*.txt')):
        key = f"{prefix}{txt_file.name}"
        s3.upload_file(str(txt_file), bucket, key)
        uploaded += 1

    print(f"Uploaded {uploaded} lecture chunks to s3://{bucket}/{prefix}")
    return uploaded


def move_processed(input_dir: str):
    """Move processed files to done/ subfolder."""
    inp = Path(input_dir)
    done = inp / 'done'
    done.mkdir(exist_ok=True)

    for txt_file in inp.glob('*.txt'):
        txt_file.rename(done / txt_file.name)
    print(f"Moved processed files to {done}/")


if __name__ == '__main__':
    input_dir = 'data/new_lectures'
    output_dir = 'data/lectures_chunked'

    Path(input_dir).mkdir(parents=True, exist_ok=True)

    print(f'Processing lectures from: {input_dir}/\n')
    chunks = process_lectures(input_dir, output_dir)

    if not chunks:
        print(f'\nDrop .txt files into {input_dir}/ and re-run.')
    else:
        print(f'\nTotal: {len(chunks)} chunks\n')
        upload_to_s3(output_dir, 'perfectpixels-kb-docs', 'kb-clean/v1/')
        move_processed(input_dir)
        print('\nDone! Sync the Bedrock KB to index the new content.')
