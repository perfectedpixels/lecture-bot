import re
from typing import List, Dict, Tuple
from dataclasses import dataclass

@dataclass
class CleanedSegment:
    """Represents a cleaned segment of transcript"""
    text: str
    original_line_start: int
    original_line_end: int
    speaker_removed: bool

class TranscriptCleaner:
    """
    Cleans lecture transcripts by removing timestamps and speaker labels.
    Preserves semantic meaning while making text more suitable for RAG.
    """
    
    def __init__(self, speaker_name: str = "Jason Levine"):
        self.speaker_name = speaker_name
        # Common timestamp patterns
        self.timestamp_patterns = [
            r'\d{1,2}:\d{2}:\d{2}',  # HH:MM:SS or H:MM:SS
            r'\d{1,2}:\d{2}',         # MM:SS or M:SS
            r'\[\d{1,2}:\d{2}:\d{2}\]',  # [HH:MM:SS]
            r'\(\d{1,2}:\d{2}:\d{2}\)',  # (HH:MM:SS)
        ]
        
    def clean_transcript(self, raw_text: str) -> str:
        """
        Main cleaning function. Removes timestamps and speaker labels.
        """
        lines = raw_text.split('\n')
        cleaned_lines = []
        
        for line in lines:
            cleaned_line = self._clean_line(line)
            if cleaned_line.strip():  # Only keep non-empty lines
                cleaned_lines.append(cleaned_line)
        
        return '\n'.join(cleaned_lines)
    
    def _clean_line(self, line: str) -> str:
        """Clean a single line of transcript"""
        # Remove timestamps
        for pattern in self.timestamp_patterns:
            line = re.sub(pattern, '', line)
        
        # Remove speaker labels (e.g., "Jason Levine:", "Jason Levine -", etc.)
        speaker_patterns = [
            rf'{self.speaker_name}\s*:',
            rf'{self.speaker_name}\s*-',
            rf'\[{self.speaker_name}\]',
            rf'{self.speaker_name}\s*\|',
        ]
        
        for pattern in speaker_patterns:
            line = re.sub(pattern, '', line, flags=re.IGNORECASE)
        
        # Clean up extra whitespace
        line = re.sub(r'\s+', ' ', line)
        line = line.strip()
        
        return line
    
    def clean_and_segment(self, raw_text: str, min_segment_length: int = 200) -> List[str]:
        """
        Clean transcript and break into semantic segments.
        Tries to keep related content together.
        """
        cleaned = self.clean_transcript(raw_text)
        
        # Split into paragraphs (double newline or more)
        paragraphs = re.split(r'\n\s*\n', cleaned)
        
        segments = []
        current_segment = []
        current_length = 0
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
                
            para_length = len(para)
            
            # If adding this paragraph keeps us under reasonable size, add it
            if current_length + para_length < 1000:  # Max segment size
                current_segment.append(para)
                current_length += para_length
            else:
                # Save current segment if it meets minimum length
                if current_length >= min_segment_length:
                    segments.append('\n\n'.join(current_segment))
                    current_segment = [para]
                    current_length = para_length
                else:
                    # Current segment too small, add paragraph anyway
                    current_segment.append(para)
                    current_length += para_length
        
        # Don't forget the last segment
        if current_segment and current_length >= min_segment_length:
            segments.append('\n\n'.join(current_segment))
        
        return segments
    
    def extract_metadata(self, raw_text: str) -> Dict[str, str]:
        """
        Extract metadata from transcript header (if present).
        Looks for patterns like "Lecture:", "Date:", "Topic:", etc.
        """
        metadata = {}
        lines = raw_text.split('\n')[:10]  # Check first 10 lines
        
        patterns = {
            'lecture': r'Lecture\s*:\s*(.+)',
            'date': r'Date\s*:\s*(.+)',
            'topic': r'Topic\s*:\s*(.+)',
            'instructor': r'Instructor\s*:\s*(.+)',
            'course': r'Course\s*:\s*(.+)',
        }
        
        for line in lines:
            for key, pattern in patterns.items():
                match = re.search(pattern, line, re.IGNORECASE)
                if match:
                    metadata[key] = match.group(1).strip()
        
        return metadata


if __name__ == "__main__":
    # Test the cleaner
    sample = """
    00:01:23 Jason Levine: Today we're going to talk about AI and design.
    00:01:45 Jason Levine: The intersection of these fields is fascinating.
    
    00:02:10 Jason Levine: Let me give you an example from my work.
    00:02:30 When we think about user experience...
    """
    
    cleaner = TranscriptCleaner()
    cleaned = cleaner.clean_transcript(sample)
    print("Cleaned transcript:")
    print(cleaned)
    print("\n" + "="*50 + "\n")
    
    segments = cleaner.clean_and_segment(sample)
    print(f"Segments ({len(segments)}):")
    for i, seg in enumerate(segments, 1):
        print(f"\nSegment {i}:")
        print(seg)
