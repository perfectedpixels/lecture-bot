import boto3
import json
from typing import List, Dict, Set
from dataclasses import dataclass, asdict

@dataclass
class ConceptTag:
    """Represents a concept extracted from text"""
    name: str
    category: str
    confidence: float
    context: str  # Brief context where concept appears

@dataclass
class TaggedSegment:
    """Text segment with extracted concepts"""
    text: str
    concepts: List[ConceptTag]
    primary_category: str
    metadata: Dict[str, str]

class ConceptExtractor:
    """
    Uses Claude via Bedrock to extract and tag concepts from lecture segments.
    """
    
    def __init__(self, model_id: str = "anthropic.claude-3-haiku-20240307-v1:0"):
        self.bedrock = boto3.client('bedrock-runtime')
        self.model_id = model_id
        
        # Predefined concept categories (can be expanded)
        self.categories = [
            "AI/Machine Learning",
            "Design",
            "User Experience",
            "Technology",
            "Biography/Personal",
            "Frameworks/Methodologies",
            "Case Studies",
            "Theory/Concepts",
            "Tools/Software",
            "Business/Strategy"
        ]
    
    def extract_concepts(self, text: str, max_concepts: int = 10) -> List[ConceptTag]:
        """
        Extract key concepts from a text segment using Claude.
        """
        
        prompt = f"""Analyze this lecture segment and extract the key concepts discussed.

For each concept, provide:
1. The concept name (2-4 words)
2. The category it belongs to (choose from: {', '.join(self.categories)})
3. A confidence score (0.0-1.0)
4. A brief context (one sentence explaining how it's used)

Lecture segment:
{text}

Return ONLY a JSON array of concepts in this exact format:
[
  {{
    "name": "concept name",
    "category": "category name",
    "confidence": 0.95,
    "context": "brief context"
  }}
]

Extract up to {max_concepts} most important concepts. Focus on substantive topics, not filler words."""

        try:
            response = self.bedrock.invoke_model(
                modelId=self.model_id,
                body=json.dumps({
                    "anthropic_version": "bedrock-2023-05-31",
                    "max_tokens": 1000,
                    "messages": [
                        {"role": "user", "content": prompt}
                    ],
                    "temperature": 0.3  # Lower temperature for more consistent extraction
                })
            )
            
            response_body = json.loads(response['body'].read())
            content = response_body['content'][0]['text']
            
            # Extract JSON from response (Claude might add explanation)
            json_match = content[content.find('['):content.rfind(']')+1]
            concepts_data = json.loads(json_match)
            
            concepts = [ConceptTag(**c) for c in concepts_data]
            return concepts
            
        except Exception as e:
            print(f"Error extracting concepts: {e}")
            return []
    
    def determine_primary_category(self, concepts: List[ConceptTag]) -> str:
        """
        Determine the primary category for a segment based on extracted concepts.
        Uses weighted voting by confidence scores.
        """
        if not concepts:
            return "General"
        
        category_scores = {}
        for concept in concepts:
            category = concept.category
            category_scores[category] = category_scores.get(category, 0) + concept.confidence
        
        primary = max(category_scores.items(), key=lambda x: x[1])
        return primary[0]
    
    def tag_segment(self, text: str, metadata: Dict[str, str] = None) -> TaggedSegment:
        """
        Fully process a segment: extract concepts and determine primary category.
        """
        concepts = self.extract_concepts(text)
        primary_category = self.determine_primary_category(concepts)
        
        return TaggedSegment(
            text=text,
            concepts=concepts,
            primary_category=primary_category,
            metadata=metadata or {}
        )
    
    def batch_tag_segments(self, segments: List[str], metadata: Dict[str, str] = None) -> List[TaggedSegment]:
        """
        Tag multiple segments. Useful for processing entire lectures.
        """
        tagged_segments = []
        
        for i, segment in enumerate(segments):
            print(f"Processing segment {i+1}/{len(segments)}...")
            tagged = self.tag_segment(segment, metadata)
            tagged_segments.append(tagged)
        
        return tagged_segments
    
    def extract_all_concepts(self, tagged_segments: List[TaggedSegment]) -> Set[str]:
        """
        Get unique set of all concepts across segments.
        Useful for building concept vocabulary.
        """
        all_concepts = set()
        for segment in tagged_segments:
            for concept in segment.concepts:
                all_concepts.add(concept.name)
        return all_concepts
    
    def to_bedrock_metadata(self, tagged_segment: TaggedSegment) -> Dict[str, str]:
        """
        Convert tagged segment to metadata format for Bedrock Knowledge Base.
        """
        # Bedrock KB metadata must be strings
        concepts_str = ", ".join([c.name for c in tagged_segment.concepts])
        categories_str = ", ".join(set([c.category for c in tagged_segment.concepts]))
        
        metadata = {
            "primary_category": tagged_segment.primary_category,
            "concepts": concepts_str,
            "categories": categories_str,
            "concept_count": str(len(tagged_segment.concepts))
        }
        
        # Add any additional metadata
        metadata.update(tagged_segment.metadata)
        
        return metadata


if __name__ == "__main__":
    # Test the extractor
    sample_text = """
    Today we're exploring the intersection of artificial intelligence and user experience design.
    When we think about designing AI-powered interfaces, we need to consider both the technical
    capabilities of machine learning models and the human factors that make interfaces intuitive.
    
    One framework I often use is the Design Thinking methodology, which helps us empathize with
    users before jumping into solutions. This is especially important in AI/UX because the
    technology can be opaque to end users.
    """
    
    extractor = ConceptExtractor()
    tagged = extractor.tag_segment(sample_text, {"lecture": "AI and Design"})
    
    print(f"Primary Category: {tagged.primary_category}")
    print(f"\nExtracted Concepts ({len(tagged.concepts)}):")
    for concept in tagged.concepts:
        print(f"  - {concept.name} ({concept.category}) - {concept.confidence:.2f}")
        print(f"    Context: {concept.context}")
