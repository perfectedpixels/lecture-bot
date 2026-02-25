#!/usr/bin/env python3
"""
Simplified Portfolio Image Tagging Tool
Tags one project at a time with progress output
"""

import json
import boto3
from pathlib import Path
from typing import List, Dict
import sys

# High-level teaching concepts taxonomy
TEACHING_CONCEPTS = [
    "Information Architecture",
    "Branding & Identity", 
    "Simplification & Clarity",
    "Interface Design",
    "Usability Testing",
    "Persona Definition",
    "AI Ethics",
    "User Research Methods",
    "Design Systems",
    "Workflow Automation",
    "Visual Design",
    "Interaction Design",
    "Content Strategy",
    "Accessibility",
    "Design Thinking",
    "Agile/Lean UX",
    "Data-Driven Design",
    "Prototyping",
    "Journey Mapping",
    "Service Design"
]

def load_image_map():
    """Load existing image map"""
    with open("data/portfolio_image_map.json", 'r') as f:
        return json.load(f)

def load_portfolio_content():
    """Load portfolio text content"""
    content_path = Path("data/perfectpixels_complete_portfolio.txt")
    if content_path.exists():
        with open(content_path, 'r') as f:
            return f.read()
    return ""

def extract_project_text(content: str, project_key: str) -> str:
    """Extract project description from portfolio content"""
    project_name = project_key.replace('-', ' ').title()
    start_idx = content.lower().find(project_name.lower())
    if start_idx == -1:
        return ""
    return content[start_idx:start_idx + 1000]

def analyze_project(bedrock, project_key: str, project_data: Dict, project_text: str) -> Dict:
    """Use Claude to analyze project and suggest tags"""
    
    prompt = f"""Analyze this UX/design portfolio project and provide metadata tags.

Project: {project_data.get('title', project_key)}
Description: {project_text}

Teaching Concepts: {', '.join(TEACHING_CONCEPTS[:10])}

For this project, provide:
1. Primary concepts (2-3 high-level teaching concepts)
2. Methodologies used
3. Key outcomes

Then for EACH image, provide tags. Images: {[img.get('filename', f'image_{i}') for i, img in enumerate(project_data.get('images', []))]}

Return ONLY valid JSON:
{{
    "primary_concepts": ["concept1", "concept2"],
    "methodologies": ["method1"],
    "outcomes": "brief outcome",
    "images": {{
        "filename.jpg": {{
            "concepts": ["tag1", "tag2"],
            "phase": "research|design|testing",
            "description": "what image shows"
        }}
    }}
}}
"""
    
    try:
        response = bedrock.invoke_model(
            modelId="anthropic.claude-3-sonnet-20240229-v1:0",
            body=json.dumps({
                "anthropic_version": "bedrock-2023-05-31",
                "max_tokens": 2000,
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.3
            })
        )
        
        content = json.loads(response['body'].read())['content'][0]['text']
        json_start = content.find('{')
        json_end = content.rfind('}') + 1
        return json.loads(content[json_start:json_end])
        
    except Exception as e:
        print(f"  ⚠️  Error: {e}")
        return {}

def main():
    print("Starting portfolio image tagging...")
    print("This will take 5-10 minutes to analyze all projects with Claude.\n")
    
    # Load data
    image_map = load_image_map()
    portfolio_content = load_portfolio_content()
    bedrock = boto3.client('bedrock-runtime')
    
    metadata = {}
    total_projects = len(image_map)
    
    for idx, (project_key, project_data) in enumerate(image_map.items(), 1):
        print(f"[{idx}/{total_projects}] Analyzing: {project_key}")
        
        # Extract project description
        project_text = extract_project_text(portfolio_content, project_key)
        
        # Analyze with Claude
        analysis = analyze_project(bedrock, project_key, project_data, project_text)
        
        if not analysis:
            print(f"  ⚠️  Skipped - analysis failed\n")
            continue
        
        # Store metadata
        metadata[project_key] = {
            'title': project_data.get('title', project_key),
            'summary': {
                'primary_concepts': analysis.get('primary_concepts', []),
                'methodologies_used': analysis.get('methodologies', []),
                'key_outcomes': analysis.get('outcomes', '')
            },
            'images': []
        }
        
        # Tag each image
        image_tags = analysis.get('images', {})
        for img in project_data.get('images', []):
            filename = img.get('filename', '')
            tags = image_tags.get(filename, {})
            
            metadata[project_key]['images'].append({
                'filename': filename,
                'path': img.get('path', ''),
                's3_url': img.get('s3_url', ''),
                'concept_tags': tags.get('concepts', []),
                'phase': tags.get('phase', 'unknown'),
                'methodology': tags.get('methodology', ''),
                'description': tags.get('description', ''),
                'teaching_concepts': []  # Will map later
            })
        
        print(f"  ✓ Tagged {len(metadata[project_key]['images'])} images\n")
    
    # Save metadata
    output_path = "data/portfolio_image_metadata.json"
    with open(output_path, 'w') as f:
        json.dump(metadata, f, indent=2)
    
    print(f"\n✅ Complete! Saved metadata to {output_path}")
    print(f"   Tagged {sum(len(p['images']) for p in metadata.values())} images across {len(metadata)} projects")
    print(f"\nNext step: Review and refine tags with:")
    print(f"   python3 scripts/tag_portfolio_images.py review")

if __name__ == "__main__":
    main()
