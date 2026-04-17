"""
Process assignment HTML files into chunked text for Bedrock KB ingestion.
Converts HTML -> clean text -> semantic chunks -> uploads to S3.
"""

import os
import re
import hashlib
import json
import boto3
from pathlib import Path
from html.parser import HTMLParser


# --- HTML to text ---

class HTMLTextExtractor(HTMLParser):
    """Strip HTML tags and extract clean text."""
    def __init__(self):
        super().__init__()
        self._text = []
        self._skip = False
        self._skip_tags = {'script', 'style', 'head'}

    def handle_starttag(self, tag, attrs):
        if tag in self._skip_tags:
            self._skip = True
        if tag in ('p', 'br', 'div', 'h1', 'h2', 'h3', 'h4', 'li', 'tr'):
            self._text.append('\n')

    def handle_endtag(self, tag):
        if tag in self._skip_tags:
            self._skip = False
        if tag in ('p', 'div', 'h1', 'h2', 'h3', 'h4', 'ul', 'ol', 'table'):
            self._text.append('\n')

    def handle_data(self, data):
        if not self._skip:
            self._text.append(data)

    def get_text(self):
        raw = ''.join(self._text)
        # Collapse whitespace
        raw = re.sub(r'[ \t]+', ' ', raw)
        raw = re.sub(r'\n{3,}', '\n\n', raw)
        return raw.strip()


def html_to_text(html_content: str) -> str:
    extractor = HTMLTextExtractor()
    extractor.feed(html_content)
    return extractor.get_text()


# --- Chunking ---

def chunk_text(text: str, max_tokens: int = 400, overlap: int = 50) -> list:
    """Split text into overlapping chunks by approximate token count."""
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


# --- Metadata tagging ---

CONCEPT_KEYWORDS = {
    'personas': ['persona', 'user persona', 'empathy map', 'archetype'],
    'heuristics': ['heuristic', 'nielsen', 'usability heuristic', 'design principle'],
    'usability': ['usability', 'usability test', 'usability study', 'usability script', 'task analysis'],
    'user-research': ['interview', 'survey', 'qualitative', 'quantitative', 'user research', 'field study'],
    'prototyping': ['prototype', 'wireframe', 'mockup', 'paper prototype', 'lo-fi', 'hi-fi'],
    'design-thinking': ['design thinking', 'ideation', 'brainstorm', 'journey map', 'storyboard'],
    'ai-design': ['ai', 'artificial intelligence', 'llm', 'agent', 'prompt', 'machine learning'],
    'presentation': ['presentation', 'pitch', 'final project', 'deliverable'],
}

def detect_concepts(text: str) -> list:
    text_lower = text.lower()
    found = []
    for concept, keywords in CONCEPT_KEYWORDS.items():
        if any(kw in text_lower for kw in keywords):
            found.append(concept)
    return found if found else ['general']


def build_metadata(filename: str, text: str, course: str) -> dict:
    concepts = detect_concepts(text)
    return {
        'doc_type': 'assignment',
        'course': course,
        'source': filename,
        'concepts': concepts,
    }


# --- Main pipeline ---

def process_course(input_dir: str, course_id: str, output_dir: str):
    """Process all HTML files in a course directory."""
    input_path = Path(input_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)

    all_chunks = []

    for html_file in sorted(input_path.glob('*.html')):
        filename = html_file.stem

        # Skip non-assignment files
        if filename in ('front-page', 'extra-credit', 'participation-during-class'):
            print(f"  Skipping {filename} (not assignment content)")
            continue

        html_content = html_file.read_text(encoding='utf-8', errors='replace')
        text = html_to_text(html_content)

        if len(text.split()) < 20:
            print(f"  Skipping {filename} (too short: {len(text.split())} words)")
            continue

        chunks = chunk_text(text, max_tokens=400, overlap=50)
        metadata = build_metadata(filename, text, course_id)

        print(f"  {filename}: {len(text.split())} words -> {len(chunks)} chunks | concepts: {metadata['concepts']}")

        for i, chunk in enumerate(chunks):
            # Generate deterministic filename
            content_hash = hashlib.md5(chunk.encode()).hexdigest()[:12]
            chunk_filename = f"assignment-{course_id}-{filename}-part-{i:04d}-{content_hash}.txt"

            # Prepend metadata header to chunk
            header = f"[Assignment: {filename.replace('-', ' ').title()}]\n[Course: COMMLD-{course_id}]\n[Concepts: {', '.join(metadata['concepts'])}]\n\n"
            chunk_with_header = header + chunk

            chunk_path = output_path / chunk_filename
            chunk_path.write_text(chunk_with_header, encoding='utf-8')

            all_chunks.append({
                'filename': chunk_filename,
                'metadata': metadata,
                'word_count': len(chunk.split()),
            })

    return all_chunks


def upload_to_s3(output_dir: str, bucket: str, prefix: str):
    """Upload chunked files to S3."""
    s3 = boto3.client('s3')
    output_path = Path(output_dir)
    uploaded = 0

    for txt_file in sorted(output_path.glob('*.txt')):
        key = f"{prefix}{txt_file.name}"
        s3.upload_file(str(txt_file), bucket, key)
        uploaded += 1

    print(f"Uploaded {uploaded} chunks to s3://{bucket}/{prefix}")
    return uploaded


if __name__ == '__main__':
    output_dir = 'data/assignments_chunked'

    print("=== Processing COMMLD-515 ===")
    chunks_515 = process_course('data/assignments_raw', '515', output_dir)

    print(f"\n=== Processing COMMLD-512 ===")
    chunks_512 = process_course('data/assignments_raw_512', '512', output_dir)

    total = len(chunks_515) + len(chunks_512)
    print(f"\n=== Total: {total} chunks ready for upload ===")

    # Upload to personal account S3
    upload = input(f"\nUpload {total} chunks to s3://perfectpixels-kb-docs/kb-clean/v1/? (y/n): ")
    if upload.lower() == 'y':
        uploaded = upload_to_s3(output_dir, 'perfectpixels-kb-docs', 'kb-clean/v1/')
        print(f"\nDone! {uploaded} chunks uploaded.")
        print("Next step: Sync the Bedrock Knowledge Base in the AWS console.")
    else:
        print(f"\nChunks saved to {output_dir}/ — upload manually when ready.")
