#!/usr/bin/env python3
"""
Complete preprocessing pipeline for lecture transcripts.
Cleans, tags, and creates affinity maps.
"""

import sys
import os
import json
import argparse
from pathlib import Path

from .transcript_cleaner import TranscriptCleaner
from .concept_extractor import ConceptExtractor, TaggedSegment
from .affinity_mapper import AffinityMapper

class LecturePreprocessingPipeline:
    """
    End-to-end pipeline for processing lecture transcripts.
    """
    
    def __init__(self, speaker_name: str = "Jason Levine"):
        self.cleaner = TranscriptCleaner(speaker_name)
        self.extractor = ConceptExtractor()
        self.mapper = AffinityMapper()
        
    def process_single_lecture(self, 
                               input_file: str, 
                               output_dir: str,
                               lecture_metadata: dict = None) -> dict:
        """
        Process a single lecture transcript through the full pipeline.
        """
        print(f"\n{'='*60}")
        print(f"Processing: {input_file}")
        print(f"{'='*60}\n")
        
        # Read raw transcript
        with open(input_file, 'r') as f:
            raw_text = f.read()
        
        # Step 1: Extract metadata
        print("Step 1: Extracting metadata...")
        metadata = self.cleaner.extract_metadata(raw_text)
        if lecture_metadata:
            metadata.update(lecture_metadata)
        print(f"  Metadata: {metadata}")
        
        # Step 2: Clean and segment
        print("\nStep 2: Cleaning and segmenting...")
        segments = self.cleaner.clean_and_segment(raw_text)
        print(f"  Created {len(segments)} segments")
        
        # Step 3: Extract concepts from each segment
        print("\nStep 3: Extracting concepts...")
        tagged_segments = self.extractor.batch_tag_segments(segments, metadata)
        
        total_concepts = sum(len(seg.concepts) for seg in tagged_segments)
        print(f"  Extracted {total_concepts} total concepts")
        
        # Step 4: Save processed segments
        print("\nStep 4: Saving processed segments...")
        output_path = Path(output_dir)
        output_path.mkdir(parents=True, exist_ok=True)
        
        lecture_name = Path(input_file).stem
        
        # Save each segment as a separate file (for Bedrock KB)
        segment_files = []
        for i, tagged_seg in enumerate(tagged_segments):
            segment_file = output_path / f"{lecture_name}_segment_{i+1}.json"
            
            segment_data = {
                'text': tagged_seg.text,
                'metadata': self.extractor.to_bedrock_metadata(tagged_seg),
                'concepts': [
                    {
                        'name': c.name,
                        'category': c.category,
                        'confidence': c.confidence
                    }
                    for c in tagged_seg.concepts
                ]
            }
            
            with open(segment_file, 'w') as f:
                json.dump(segment_data, f, indent=2)
            
            segment_files.append(str(segment_file))
        
        print(f"  Saved {len(segment_files)} segment files")
        
        # Save summary
        summary_file = output_path / f"{lecture_name}_summary.json"
        summary = {
            'lecture_name': lecture_name,
            'metadata': metadata,
            'segment_count': len(tagged_segments),
            'total_concepts': total_concepts,
            'unique_concepts': len(self.extractor.extract_all_concepts(tagged_segments)),
            'categories': list(set(seg.primary_category for seg in tagged_segments)),
            'segment_files': segment_files
        }
        
        with open(summary_file, 'w') as f:
            json.dump(summary, f, indent=2)
        
        print(f"  Saved summary to {summary_file}")
        
        return {
            'tagged_segments': tagged_segments,
            'summary': summary
        }
    
    def process_multiple_lectures(self, 
                                  input_dir: str, 
                                  output_dir: str,
                                  create_affinity_map: bool = True) -> dict:
        """
        Process multiple lectures and create affinity map across all.
        """
        input_path = Path(input_dir)
        transcript_files = list(input_path.glob('*.txt'))
        
        if not transcript_files:
            print(f"No .txt files found in {input_dir}")
            return {}
        
        print(f"\nFound {len(transcript_files)} transcript files")
        
        all_tagged_segments = []
        all_summaries = []
        
        # Process each lecture
        for transcript_file in transcript_files:
            result = self.process_single_lecture(
                str(transcript_file),
                output_dir
            )
            all_tagged_segments.extend(result['tagged_segments'])
            all_summaries.append(result['summary'])
        
        # Create affinity map across all lectures
        if create_affinity_map and all_tagged_segments:
            print(f"\n{'='*60}")
            print("Creating affinity map across all lectures...")
            print(f"{'='*60}\n")
            
            # Build co-occurrence matrix
            self.mapper.build_cooccurrence_matrix(all_tagged_segments)
            
            # Get all unique concepts
            all_concepts = list(self.extractor.extract_all_concepts(all_tagged_segments))
            print(f"Total unique concepts: {len(all_concepts)}")
            
            # Create semantic clusters
            print("\nCreating semantic clusters...")
            num_clusters = min(10, len(all_concepts) // 3)  # Adaptive cluster count
            clusters = self.mapper.create_semantic_clusters(all_concepts, num_clusters)
            
            # Enrich with metadata
            clusters = self.mapper.enrich_clusters_with_metadata(clusters, all_tagged_segments)
            
            print(f"\nCreated {len(clusters)} concept clusters:")
            for cluster in clusters:
                print(f"  - {cluster.cluster_id}: {len(cluster.concepts)} concepts, "
                      f"{cluster.segment_count} segments, "
                      f"affinity: {cluster.affinity_score:.2f}")
            
            # Export affinity map
            affinity_file = Path(output_dir) / "affinity_map.json"
            self.mapper.export_affinity_map(clusters, str(affinity_file))
            
            # Save master index
            master_index = {
                'total_lectures': len(transcript_files),
                'total_segments': len(all_tagged_segments),
                'total_concepts': len(all_concepts),
                'clusters': len(clusters),
                'lectures': all_summaries,
                'affinity_map_file': str(affinity_file)
            }
            
            index_file = Path(output_dir) / "master_index.json"
            with open(index_file, 'w') as f:
                json.dump(master_index, f, indent=2)
            
            print(f"\nMaster index saved to {index_file}")
        
        return {
            'tagged_segments': all_tagged_segments,
            'summaries': all_summaries
        }


PreprocessingPipeline = LecturePreprocessingPipeline  # alias for streamlit_app


def main():
    parser = argparse.ArgumentParser(
        description='Preprocess lecture transcripts for AI chatbot'
    )
    parser.add_argument('input', help='Input file or directory')
    parser.add_argument('output', help='Output directory')
    parser.add_argument('--speaker', default='Jason Levine', 
                       help='Speaker name to remove from transcripts')
    parser.add_argument('--no-affinity', action='store_true',
                       help='Skip affinity map creation')
    
    args = parser.parse_args()
    
    pipeline = LecturePreprocessingPipeline(speaker_name=args.speaker)
    
    input_path = Path(args.input)
    
    if input_path.is_file():
        # Process single file
        pipeline.process_single_lecture(args.input, args.output)
    elif input_path.is_dir():
        # Process directory
        pipeline.process_multiple_lectures(
            args.input, 
            args.output,
            create_affinity_map=not args.no_affinity
        )
    else:
        print(f"Error: {args.input} is not a valid file or directory")
        sys.exit(1)
    
    print("\n✓ Processing complete!")


if __name__ == "__main__":
    main()
