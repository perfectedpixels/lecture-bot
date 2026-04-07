#!/usr/bin/env python3
"""
Lecture-Portfolio Cross-Reference Tool
Extract portfolio project mentions from lecture transcripts
"""

import json
import os
import sys
from pathlib import Path
from typing import List, Dict, Set
import re

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'src'))
from llm_client import call_claude, DEFAULT_MODEL

class LecturePortfolioCrossReferencer:
    """Cross-reference portfolio projects with lecture mentions"""
    
    def __init__(self):
        self.portfolio_metadata = self._load_portfolio_metadata()
        self.project_names = self._extract_project_names()
    
    def _load_portfolio_metadata(self) -> Dict:
        """Load existing portfolio metadata"""
        with open('data/portfolio_image_metadata.json', 'r') as f:
            return json.load(f)
    
    def _extract_project_names(self) -> Dict[str, List[str]]:
        """Extract project names and variations for matching"""
        project_names = {}
        
        for project_key, project_data in self.portfolio_metadata.items():
            # Get title variations
            title = project_data.get('title', project_key)
            variations = [
                project_key,
                title,
                project_key.replace('-', ' '),
                title.lower(),
                project_key.replace('-', ' ').title()
            ]
            project_names[project_key] = list(set(variations))
        
        return project_names
    
    def find_mentions_in_transcript(self, transcript_path: str) -> Dict[str, List[Dict]]:
        """Find portfolio project mentions in a transcript"""
        
        with open(transcript_path, 'r') as f:
            transcript = f.read()
        
        mentions = {}
        
        # Search for each project
        for project_key, variations in self.project_names.items():
            project_mentions = []
            
            for variation in variations:
                # Case-insensitive search
                pattern = re.compile(re.escape(variation), re.IGNORECASE)
                for match in pattern.finditer(transcript):
                    # Get context around mention (200 chars before/after)
                    start = max(0, match.start() - 200)
                    end = min(len(transcript), match.end() + 200)
                    context = transcript[start:end]
                    
                    project_mentions.append({
                        'position': match.start(),
                        'matched_text': match.group(),
                        'context': context.strip()
                    })
            
            if project_mentions:
                mentions[project_key] = project_mentions
        
        return mentions
    
    def analyze_mention_context(self, project_key: str, mention: Dict) -> Dict:
        """Use Claude to analyze the context of a portfolio mention"""
        
        prompt = f"""Analyze this mention of a portfolio project in a lecture transcript.

Project: {project_key}
Context: {mention['context']}

Determine:
1. What aspect of the project is being discussed? (research, design, testing, outcome, etc.)
2. What teaching concept is being illustrated? (from the context)
3. Is this a brief mention or detailed discussion?
4. What is the key takeaway or lesson being taught?

Return ONLY valid JSON:
{{
    "aspect": "research|design|testing|outcome|process",
    "teaching_concept": "specific concept being taught",
    "mention_type": "brief|detailed",
    "key_takeaway": "main lesson or point",
    "relevance_score": 0.0-1.0
}}
"""
        
        try:
            content = call_claude(prompt, max_tokens=500, temperature=0.3)
            json_start = content.find('{')
            json_end = content.rfind('}') + 1
            return json.loads(content[json_start:json_end])
            
        except Exception as e:
            print(f"  ⚠️  Error analyzing mention: {e}")
            return {}
    
    def process_all_transcripts(self, transcript_dir: str = "data/canvas_extracted_512"):
        """Process all lecture transcripts and find portfolio mentions"""
        
        transcript_path = Path(transcript_dir)
        all_mentions = {}
        
        print("Searching for portfolio mentions in lecture transcripts...\n")
        
        for transcript_file in transcript_path.glob("*.txt"):
            print(f"Processing: {transcript_file.name}")
            
            mentions = self.find_mentions_in_transcript(str(transcript_file))
            
            if mentions:
                print(f"  Found mentions in {len(mentions)} projects")
                
                for project_key, project_mentions in mentions.items():
                    if project_key not in all_mentions:
                        all_mentions[project_key] = []
                    
                    # Analyze each mention
                    for mention in project_mentions:
                        print(f"    Analyzing {project_key} mention...")
                        analysis = self.analyze_mention_context(project_key, mention)
                        
                        if analysis:
                            all_mentions[project_key].append({
                                'lecture_file': transcript_file.name,
                                'context': mention['context'],
                                'analysis': analysis
                            })
        
        return all_mentions
    
    def update_portfolio_metadata(self, mentions: Dict):
        """Add lecture mentions to portfolio metadata"""
        
        for project_key, project_mentions in mentions.items():
            if project_key in self.portfolio_metadata:
                self.portfolio_metadata[project_key]['lecture_mentions'] = project_mentions
        
        # Save updated metadata
        with open('data/portfolio_image_metadata.json', 'w') as f:
            json.dump(self.portfolio_metadata, f, indent=2)
        
        print(f"\n✓ Updated portfolio metadata with lecture cross-references")
    
    def generate_report(self, mentions: Dict):
        """Generate a summary report of cross-references"""
        
        print("\n" + "="*60)
        print("LECTURE-PORTFOLIO CROSS-REFERENCE REPORT")
        print("="*60 + "\n")
        
        total_mentions = sum(len(m) for m in mentions.values())
        print(f"Total projects mentioned: {len(mentions)}")
        print(f"Total mentions found: {total_mentions}\n")
        
        for project_key, project_mentions in sorted(mentions.items()):
            print(f"\n{project_key.upper()}")
            print(f"  Mentions: {len(project_mentions)}")
            
            # Group by teaching concept
            concepts = {}
            for mention in project_mentions:
                concept = mention['analysis'].get('teaching_concept', 'unknown')
                concepts[concept] = concepts.get(concept, 0) + 1
            
            print(f"  Teaching concepts: {', '.join(concepts.keys())}")
            
            # Show high-relevance mentions
            high_relevance = [m for m in project_mentions 
                            if m['analysis'].get('relevance_score', 0) > 0.7]
            if high_relevance:
                print(f"  High-relevance mentions: {len(high_relevance)}")


def main():
    print("Starting lecture-portfolio cross-reference analysis...\n")
    
    cross_ref = LecturePortfolioCrossReferencer()
    
    # Find all mentions
    mentions = cross_ref.process_all_transcripts()
    
    # Update metadata
    if mentions:
        cross_ref.update_portfolio_metadata(mentions)
        cross_ref.generate_report(mentions)
    else:
        print("\n⚠️  No portfolio mentions found in transcripts")
    
    print("\n✓ Cross-reference analysis complete!")


if __name__ == "__main__":
    main()
