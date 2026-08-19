"""
Process grading handbook into chunked text for Bedrock KB ingestion.
Splits course-level policy from per-assignment rubrics.

Usage:
    python3 scripts/process_grading.py

To update: edit data/grading/grading-handbook-512-515.txt, then re-run this script.
It will re-chunk and re-upload, replacing previous grading chunks in S3.
"""

import re
import hashlib
import boto3
from pathlib import Path

from kb_metadata import write_sidecar, upload_chunk_with_sidecar


ASSIGNMENT_MAP = {
    'Assignment 2.1: Persona Development': {
        'name': 'persona-development',
        'concepts': ['personas', 'user-research'],
        'linked_assignments': ['user-persona', 'building-user-personas', 'ai-agent-persona-1-of-2'],
    },
    'Assignment 3: Customer Journey Map': {
        'name': 'customer-journey-map',
        'concepts': ['personas', 'design-thinking', 'user-research'],
        'linked_assignments': ['customer-journey-map-and-product-experience-storyboard'],
    },
    'Assignment 4: Paper Prototype': {
        'name': 'paper-prototype',
        'concepts': ['prototyping', 'design-thinking'],
        'linked_assignments': ['paper-prototype-2-of-2', 'final-prototype'],
    },
    'Assignment 5: Wireframes': {
        'name': 'wireframes',
        'concepts': ['prototyping', 'design-thinking'],
        'linked_assignments': ['wireframes'],
    },
    'Assignment 2: Design Aesthetics Evaluation': {
        'name': 'design-aesthetics',
        'concepts': ['heuristics', 'design-thinking'],
        'linked_assignments': ['identifying-design-principles'],
    },
    'Assignment 6: Heuristic Evaluation': {
        'name': 'heuristic-evaluation',
        'concepts': ['heuristics', 'usability'],
        'linked_assignments': ['heuristics-report'],
    },
}


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


def split_handbook(filepath: str) -> tuple:
    """Split handbook into course-level policy and per-assignment rubrics."""
    text = Path(filepath).read_text(encoding='utf-8')

    # Split on the rubrics marker
    if '--- ASSIGNMENT RUBRICS ---' in text:
        parts = text.split('--- ASSIGNMENT RUBRICS ---')
        course_policy = parts[0].strip()
        rubrics_and_notes = parts[1]
    else:
        course_policy = text
        rubrics_and_notes = ''

    # Split instructor notes from rubrics
    if '--- INSTRUCTOR NOTES ---' in rubrics_and_notes:
        rubric_parts = rubrics_and_notes.split('--- INSTRUCTOR NOTES ---')
        rubrics_text = rubric_parts[0].strip()
        instructor_notes = rubric_parts[1].strip()
        # Instructor notes are course-level
        course_policy += '\n\n' + instructor_notes
    else:
        rubrics_text = rubrics_and_notes.strip()

    # Split rubrics into individual assignments
    assignment_rubrics = {}
    current_key = None
    current_lines = []

    for line in rubrics_text.split('\n'):
        # Check if this line starts a new assignment section
        matched = False
        for key in ASSIGNMENT_MAP:
            if line.strip().startswith(key):
                if current_key and current_lines:
                    assignment_rubrics[current_key] = '\n'.join(current_lines).strip()
                current_key = key
                current_lines = [line]
                matched = True
                break
        if not matched:
            current_lines.append(line)

    if current_key and current_lines:
        assignment_rubrics[current_key] = '\n'.join(current_lines).strip()

    return course_policy, assignment_rubrics


def process_grading_handbook(filepath: str, output_dir: str) -> list:
    """Process handbook into tagged chunks."""
    out = Path(output_dir)
    out.mkdir(parents=True, exist_ok=True)

    course_policy, assignment_rubrics = split_handbook(filepath)
    all_chunks = []

    # --- Course-level policy chunks ---
    print('=== Course Policy ===')
    policy_chunks = chunk_text(course_policy, max_tokens=400, overlap=50)
    for i, chunk in enumerate(policy_chunks):
        content_hash = hashlib.md5(chunk.encode()).hexdigest()[:12]
        filename = f"grading-course-policy-part-{i:04d}-{content_hash}.txt"

        header = "[Course Policy: UX Research & Strategy Grading]\n[Applies to: COMMLD-512, COMMLD-515]\n[Type: course-policy]\n\n"
        chunk_path = out / filename
        chunk_path.write_text(header + chunk, encoding='utf-8')
        write_sidecar(chunk_path, layer="directive", doc_type="course-policy")
        all_chunks.append(filename)

    print(f"  {len(policy_chunks)} chunks")

    # --- Per-assignment rubric chunks ---
    print('\n=== Assignment Rubrics ===')
    for assignment_key, rubric_text in assignment_rubrics.items():
        meta = ASSIGNMENT_MAP.get(assignment_key, {})
        name = meta.get('name', 'unknown')
        concepts = meta.get('concepts', ['general'])
        linked = meta.get('linked_assignments', [])

        rubric_chunks = chunk_text(rubric_text, max_tokens=400, overlap=50)
        for i, chunk in enumerate(rubric_chunks):
            content_hash = hashlib.md5(chunk.encode()).hexdigest()[:12]
            filename = f"grading-rubric-{name}-part-{i:04d}-{content_hash}.txt"

            header = (
                f"[Rubric: {assignment_key}]\n"
                f"[Concepts: {', '.join(concepts)}]\n"
                f"[Related assignments: {', '.join(linked)}]\n"
                f"[Type: rubric]\n\n"
            )
            chunk_path = out / filename
            chunk_path.write_text(header + chunk, encoding='utf-8')
            write_sidecar(chunk_path, layer="directive", doc_type="rubric", assignment=name, concepts=concepts)
            all_chunks.append(filename)

        print(f"  {name}: {len(rubric_chunks)} chunks | concepts: {concepts}")

    return all_chunks


def upload_to_s3(output_dir: str, bucket: str, prefix: str):
    """Upload chunks, replacing any previous grading chunks."""
    s3 = boto3.client('s3')
    out = Path(output_dir)

    # Delete old grading chunks first
    paginator = s3.get_paginator('list_objects_v2')
    deleted = 0
    for page in paginator.paginate(Bucket=bucket, Prefix=prefix):
        for obj in page.get('Contents', []):
            if obj['Key'].split('/')[-1].startswith('grading-'):
                s3.delete_object(Bucket=bucket, Key=obj['Key'])
                deleted += 1
    if deleted:
        print(f"Deleted {deleted} old grading chunks from S3")

    # Upload new chunks (+ their .metadata.json sidecars, if present)
    uploaded = 0
    for txt_file in sorted(out.glob('grading-*.txt')):
        key = f"{prefix}{txt_file.name}"
        upload_chunk_with_sidecar(s3, txt_file, bucket, key)
        uploaded += 1

    print(f"Uploaded {uploaded} grading chunks to s3://{bucket}/{prefix}")
    return uploaded


if __name__ == '__main__':
    source = 'data/grading/grading-handbook-512-515.txt'
    output = 'data/grading_chunked'

    print(f'Processing: {source}\n')
    chunks = process_grading_handbook(source, output)
    print(f'\nTotal: {len(chunks)} chunks\n')

    upload_to_s3(output, 'perfectpixels-kb-docs', 'kb-clean/v1/')
    print('\nDone! Sync the Bedrock KB to index the new content.')
