#!/usr/bin/env python3
"""
Extract text content from Canvas export for Knowledge Base.
Filters out images, videos, and extracts clean text from HTML.
"""

import os
import json
import re
from pathlib import Path
from html.parser import HTMLParser
import argparse

class HTMLTextExtractor(HTMLParser):
    """Extract clean text from HTML"""
    def __init__(self):
        super().__init__()
        self.text = []
        self.skip = False
        
    def handle_starttag(self, tag, attrs):
        # Skip script and style tags
        if tag in ['script', 'style']:
            self.skip = True
            
    def handle_endtag(self, tag):
        if tag in ['script', 'style']:
            self.skip = False
            
    def handle_data(self, data):
        if not self.skip:
            text = data.strip()
            if text:
                self.text.append(text)
                
    def get_text(self):
        return '\n'.join(self.text)

def extract_html_text(html_content):
    """Extract clean text from HTML"""
    parser = HTMLTextExtractor()
    parser.feed(html_content)
    return parser.get_text()

def process_canvas_export(export_dir, output_dir):
    """Process Canvas export and extract text content"""
    
    export_path = Path(export_dir)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    stats = {
        'pages': 0,
        'assignments': 0,
        'discussions': 0,
        'total_chars': 0
    }
    
    # Process wiki pages (course content)
    wiki_dir = export_path / 'wiki_content'
    if wiki_dir.exists():
        print(f"\n📄 Processing course pages...")
        for html_file in wiki_dir.glob('*.html'):
            with open(html_file, 'r', encoding='utf-8') as f:
                html = f.read()
                text = extract_html_text(html)
                
                if len(text) > 100:  # Skip empty pages
                    output_file = output_path / f"page_{html_file.stem}.txt"
                    with open(output_file, 'w', encoding='utf-8') as out:
                        out.write(f"Course Page: {html_file.stem}\n\n")
                        out.write(text)
                    
                    stats['pages'] += 1
                    stats['total_chars'] += len(text)
                    print(f"  ✓ {html_file.name} → {len(text)} chars")
    
    # Process assignments
    assignments_file = export_path / 'assignment_groups.xml'
    if assignments_file.exists():
        print(f"\n📝 Processing assignments...")
        # Parse XML and extract assignment descriptions
        # (Simplified - you may need to adjust based on Canvas XML structure)
        with open(assignments_file, 'r', encoding='utf-8') as f:
            content = f.read()
            # Extract assignment text (basic approach)
            assignments = re.findall(r'<title>(.*?)</title>.*?<description>(.*?)</description>', 
                                    content, re.DOTALL)
            
            for i, (title, desc) in enumerate(assignments):
                text = extract_html_text(desc)
                if len(text) > 50:
                    output_file = output_path / f"assignment_{i+1}_{title[:30]}.txt"
                    with open(output_file, 'w', encoding='utf-8') as out:
                        out.write(f"Assignment: {title}\n\n")
                        out.write(text)
                    
                    stats['assignments'] += 1
                    stats['total_chars'] += len(text)
                    print(f"  ✓ {title} → {len(text)} chars")
    
    # Process discussions
    discussions_dir = export_path / 'discussion_topics'
    if discussions_dir.exists():
        print(f"\n💬 Processing discussions...")
        for html_file in discussions_dir.glob('*.html'):
            with open(html_file, 'r', encoding='utf-8') as f:
                html = f.read()
                text = extract_html_text(html)
                
                if len(text) > 50:
                    output_file = output_path / f"discussion_{html_file.stem}.txt"
                    with open(output_file, 'w', encoding='utf-8') as out:
                        out.write(f"Discussion: {html_file.stem}\n\n")
                        out.write(text)
                    
                    stats['discussions'] += 1
                    stats['total_chars'] += len(text)
                    print(f"  ✓ {html_file.name} → {len(text)} chars")
    
    # Summary
    print(f"\n✅ Extraction Complete!")
    print(f"   Pages: {stats['pages']}")
    print(f"   Assignments: {stats['assignments']}")
    print(f"   Discussions: {stats['discussions']}")
    print(f"   Total characters: {stats['total_chars']:,}")
    print(f"   Output directory: {output_path}")
    
    return stats

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='Extract text from Canvas export')
    parser.add_argument('export_dir', help='Path to extracted Canvas export directory')
    parser.add_argument('--output', default='data/canvas_extracted', 
                       help='Output directory for extracted text files')
    
    args = parser.parse_args()
    
    process_canvas_export(args.export_dir, args.output)
