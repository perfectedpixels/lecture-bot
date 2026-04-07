#!/usr/bin/env python3
"""
Portfolio Image Tagging Tool
Semi-automated tagging of portfolio images with concept metadata
"""

import json
import os
from pathlib import Path
from typing import List, Dict
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from llm_client import call_claude, DEFAULT_MODEL

class PortfolioImageTagger:
    """Tag portfolio images with concept metadata using Claude"""
    
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
    
    # Project phases
    PHASES = [
        "research",
        "ideation",
        "design",
        "prototyping",
        "testing",
        "implementation",
        "analysis"
    ]
    
    # Common methodologies
    METHODOLOGIES = [
        "contextual inquiry",
        "user interviews",
        "surveys",
        "usability testing",
        "A/B testing",
        "card sorting",
        "heuristic evaluation",
        "design thinking",
        "agile",
        "lean UX",
        "design sprints"
    ]
    
    def __init__(self, image_map_path: str = "data/portfolio_image_map.json"):
        self.model_id = DEFAULT_MODEL
        self.image_map_path = image_map_path
        self.image_map = self._load_image_map()
        self.portfolio_content = self._load_portfolio_content()
    
    def _load_image_map(self) -> Dict:
        """Load existing image map"""
        with open(self.image_map_path, 'r') as f:
            return json.load(f)
    
    def _load_portfolio_content(self) -> Dict:
        """Load portfolio text content"""
        content_path = Path("data/perfectpixels_complete_portfolio.txt")
        if content_path.exists():
            with open(content_path, 'r') as f:
                return {'text': f.read()}
        return {}
    
    def analyze_project_with_claude(self, project_key: str, project_data: Dict) -> Dict:
        """Use Claude to analyze project and suggest tags"""
        
        # Get project description from portfolio content
        project_text = self._extract_project_text(project_key)
        
        prompt = f"""Analyze this UX/design portfolio project and provide metadata tags.

Project: {project_data.get('title', project_key)}
Description: {project_text[:1000]}

Available Teaching Concepts:
{', '.join(self.TEACHING_CONCEPTS)}

Available Phases:
{', '.join(self.PHASES)}

Available Methodologies:
{', '.join(self.METHODOLOGIES)}

For each image in this project, provide:
1. Concept tags (which teaching concepts are demonstrated)
2. Phase (which phase of the design process)
3. Methodology (which methods were used)
4. Brief description (what the image shows)

Return ONLY valid JSON in this format:
{{
    "project_summary": {{
        "primary_concepts": ["concept1", "concept2"],
        "methodologies_used": ["method1", "method2"],
        "key_outcomes": "brief outcome description"
    }},
    "image_tags": {{
        "image_1.jpg": {{
            "concept_tags": ["concept1"],
            "phase": "research",
            "methodology": "user interviews",
            "description": "what the image shows"
        }}
    }}
}}

Images in project: {[img['filename'] for img in project_data.get('images', [])]}
"""
        
        try:
            content = call_claude(prompt, max_tokens=2000, temperature=0.3, model=self.model_id)
            # Extract JSON from response
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            return json.loads(content[json_start:json_end])
            
        except Exception as e:
            print(f"Error analyzing project {project_key}: {e}")
            return {}
    
    def _extract_project_text(self, project_key: str) -> str:
        """Extract project description from portfolio content"""
        # Simple extraction - can be enhanced
        content = self.portfolio_content.get('text', '')
        # Look for project section
        project_name = project_key.replace('-', ' ').title()
        start_idx = content.lower().find(project_name.lower())
        if start_idx == -1:
            return ""
        # Get next 500 characters
        return content[start_idx:start_idx + 500]
    
    def tag_all_projects(self, output_path: str = "data/portfolio_image_metadata.json"):
        """Tag all projects and save metadata"""
        
        metadata = {}
        
        for project_key, project_data in self.image_map.items():
            print(f"\nAnalyzing project: {project_key}")
            
            # Get Claude's analysis
            analysis = self.analyze_project_with_claude(project_key, project_data)
            
            if not analysis:
                print(f"  ⚠️  Skipping {project_key} - analysis failed")
                continue
            
            # Store metadata
            metadata[project_key] = {
                'title': project_data.get('title', project_key),
                'summary': analysis.get('project_summary', {}),
                'images': []
            }
            
            # Tag each image
            image_tags = analysis.get('image_tags', {})
            for img in project_data.get('images', []):
                filename = img.get('filename', '')
                tags = image_tags.get(filename, {})
                
                metadata[project_key]['images'].append({
                    'filename': filename,
                    'path': img.get('path', ''),
                    's3_url': img.get('s3_url', ''),
                    'concept_tags': tags.get('concept_tags', []),
                    'phase': tags.get('phase', 'unknown'),
                    'methodology': tags.get('methodology', ''),
                    'description': tags.get('description', ''),
                    'teaching_concepts': self._map_to_teaching_concepts(tags.get('concept_tags', []))
                })
            
            print(f"  ✓ Tagged {len(metadata[project_key]['images'])} images")
        
        # Save metadata
        with open(output_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        print(f"\n✓ Saved metadata to {output_path}")
        return metadata
    
    def _map_to_teaching_concepts(self, concept_tags: List[str]) -> List[str]:
        """Map specific tags to high-level teaching concepts"""
        # Simple mapping - can be enhanced with fuzzy matching
        teaching_concepts = []
        
        tag_mapping = {
            'user research': 'User Research Methods',
            'interviews': 'User Research Methods',
            'surveys': 'User Research Methods',
            'persona': 'Persona Definition',
            'journey map': 'Journey Mapping',
            'wireframe': 'Interface Design',
            'prototype': 'Prototyping',
            'usability': 'Usability Testing',
            'information architecture': 'Information Architecture',
            'ia': 'Information Architecture',
            'branding': 'Branding & Identity',
            'visual design': 'Visual Design',
            'interaction': 'Interaction Design',
            'accessibility': 'Accessibility',
            'design system': 'Design Systems'
        }
        
        for tag in concept_tags:
            tag_lower = tag.lower()
            for key, concept in tag_mapping.items():
                if key in tag_lower and concept not in teaching_concepts:
                    teaching_concepts.append(concept)
        
        return teaching_concepts
    
    def review_and_edit(self, metadata_path: str = "data/portfolio_image_metadata.json"):
        """Interactive review and editing of tags"""
        
        with open(metadata_path, 'r') as f:
            metadata = json.load(f)
        
        print("\n=== Portfolio Image Metadata Review ===\n")
        
        for project_key, project_data in metadata.items():
            print(f"\nProject: {project_data['title']}")
            print(f"Primary Concepts: {', '.join(project_data['summary'].get('primary_concepts', []))}")
            print(f"Images: {len(project_data['images'])}")
            
            review = input("Review images? (y/n/q to quit): ").lower()
            if review == 'q':
                break
            if review != 'y':
                continue
            
            for img in project_data['images']:
                print(f"\n  Image: {img.get('filename', 'unknown')}")
                print(f"  Description: {img.get('description', 'N/A')}")
                print(f"  Concepts: {', '.join(img.get('concept_tags', []))}")
                print(f"  Phase: {img.get('phase', 'N/A')}")
                # Methodology field is optional
                if 'methodology' in img:
                    print(f"  Methodology: {img['methodology']}")
                
                edit = input("  Edit? (y/n): ").lower()
                if edit == 'y':
                    # Allow editing
                    current_desc = img.get('description', '')
                    img['description'] = input(f"  New description [{current_desc}]: ") or current_desc
                    
                    current_concepts = img.get('concept_tags', [])
                    new_concepts = input(f"  New concepts [{', '.join(current_concepts)}]: ")
                    if new_concepts:
                        img['concept_tags'] = [c.strip() for c in new_concepts.split(',')]
                    
                    current_phase = img.get('phase', 'unknown')
                    img['phase'] = input(f"  New phase [{current_phase}]: ") or current_phase
        
        # Save edited metadata
        with open(metadata_path, 'w') as f:
            json.dump(metadata, f, indent=2)
        
        print(f"\n✓ Saved edited metadata to {metadata_path}")


def main():
    if len(sys.argv) < 2:
        print("Usage: python tag_portfolio_images.py [tag|review]")
        print("  tag    - Auto-tag all images with Claude")
        print("  review - Review and edit existing tags")
        sys.exit(1)
    
    command = sys.argv[1]
    tagger = PortfolioImageTagger()
    
    if command == 'tag':
        print("Starting automated tagging with Claude...")
        tagger.tag_all_projects()
        print("\nDone! Review the output in data/portfolio_image_metadata.json")
        print("Run 'python tag_portfolio_images.py review' to review and edit")
    
    elif command == 'review':
        print("Starting interactive review...")
        tagger.review_and_edit()
    
    else:
        print(f"Unknown command: {command}")
        sys.exit(1)


if __name__ == "__main__":
    main()
