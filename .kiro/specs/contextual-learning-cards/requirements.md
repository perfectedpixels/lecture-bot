# Contextual Learning Cards - Requirements

## Feature Overview
Replace generic "Dive deeper" buttons with intelligent, contextual learning cards that provide three types of exploration paths: related concepts from affinity mapping, high-level teaching concepts, and real-world portfolio examples.

## User Stories

### US-1: As a student, I want to see related concepts after each bot response
**So that** I can explore connected topics and deepen my understanding

**Acceptance Criteria:**
- AC-1.1: After each bot response, a "Related Concepts" card appears
- AC-1.2: Card shows 3-5 concepts from the affinity map clusters
- AC-1.3: Concepts are clickable and expand inline with mini-lessons
- AC-1.4: Expanded content pulls from knowledge base segments
- AC-1.5: Card only appears when relevant concepts exist

### US-2: As a student, I want to explore high-level teaching concepts
**So that** I can understand the broader frameworks and methodologies

**Acceptance Criteria:**
- AC-2.1: A "Core Teaching Concepts" card appears after bot responses
- AC-2.2: Shows 3-5 high-level concepts (e.g., Information Architecture, Usability Testing, AI Ethics)
- AC-2.3: Concepts are clickable and expand inline with definitions and examples
- AC-2.4: Content is curated from a predefined taxonomy of teaching concepts
- AC-2.5: Concepts relate to the current discussion topic

### US-3: As a student, I want to see real-world examples from portfolio projects
**So that** I can understand how concepts are applied in practice

**Acceptance Criteria:**
- AC-3.1: A "See It in Practice" card appears when portfolio examples are relevant
- AC-3.2: Shows 1-3 portfolio projects with images and descriptions
- AC-3.3: Projects are cross-referenced with lecture mentions
- AC-3.4: Clicking expands to show project details, methodologies used, and outcomes
- AC-3.5: Images are properly tagged with concept metadata

### US-4: As a student, I want cards to guide me to deeper related topics
**So that** I can follow a natural learning progression

**Acceptance Criteria:**
- AC-4.1: Cards suggest concepts that build on the current discussion
- AC-4.2: Suggestions lead to additional related concepts or deeper dives
- AC-4.3: Card content adapts based on what was just discussed
- AC-4.4: No duplicate suggestions from previous responses in the same session

### US-5: As a student, I want inline expansion of topics
**So that** I can explore without losing context of the conversation

**Acceptance Criteria:**
- AC-5.1: Clicking a topic expands content inline (not a new query)
- AC-5.2: Expanded content shows key points from knowledge base
- AC-5.3: Expansion includes a "Learn more" button to submit as full query
- AC-5.4: Multiple topics can be expanded simultaneously
- AC-5.5: Expanded sections are collapsible

## Data Requirements

### DR-1: Affinity Map Enhancement
**Current State:** Affinity map exists with concept clusters and relationships
**Needed:**
- Cluster metadata: difficulty level, prerequisites, related teaching concepts
- Concept descriptions (1-2 sentences) for inline expansion
- Lecture segment IDs associated with each concept

### DR-2: Teaching Concepts Taxonomy
**Current State:** Concepts are extracted but not categorized as "teaching concepts"
**Needed:**
- Curated list of high-level teaching concepts:
  - Information Architecture
  - Branding & Identity
  - Simplification & Clarity
  - Interface Design
  - Usability Testing
  - Persona Definition
  - AI Ethics
  - User Research Methods
  - Design Systems
  - Workflow Automation
  - (and more...)
- Each concept needs: definition, key principles, related affinity clusters
- Mapping from affinity clusters to teaching concepts

### DR-3: Portfolio-Lecture Cross-Reference
**Current State:** Portfolio content extracted, but not linked to lecture mentions
**Needed:**
- Identify which portfolio projects are mentioned in which lectures
- Extract context: what methodology/concept was being discussed
- Tag portfolio images with:
  - Concept tags (e.g., "user research", "information architecture")
  - Project phase (e.g., "research", "design", "testing")
  - Methodology used (e.g., "design thinking", "agile")
  - Outcome/metric (e.g., "+$350M revenue", "250M users")

### DR-4: Portfolio Image Metadata
**Current State:** Images exist but lack semantic tagging
**Needed:**
- Image metadata schema:
  ```json
  {
    "image_id": "indeed_research_1.jpg",
    "project": "Indeed Redesign",
    "concept_tags": ["user research", "persona definition", "journey mapping"],
    "phase": "research",
    "description": "User interview session with job seekers",
    "methodology": "contextual inquiry",
    "teaching_concepts": ["User Research Methods", "Persona Definition"]
  }
  ```
- Metadata for all 208 portfolio images
- Searchable by concept, methodology, or teaching concept

## Technical Requirements

### TR-1: Enhanced Bot Response Structure
**Current:** Bot returns `{answer, sources, relevant_concepts, context, safety_triggered}`
**Enhanced:** Add new fields:
```python
{
    'answer': str,
    'sources': List[str],
    'relevant_concepts': List[str],
    'context': str,
    'safety_triggered': bool,
    'learning_cards': {
        'related_concepts': [
            {
                'name': str,
                'cluster_id': str,
                'preview': str,  # 1-2 sentence description
                'segment_ids': List[str]  # For inline expansion
            }
        ],
        'teaching_concepts': [
            {
                'name': str,
                'definition': str,
                'key_principles': List[str],
                'related_clusters': List[str]
            }
        ],
        'portfolio_examples': [
            {
                'project_name': str,
                'description': str,
                'images': List[dict],  # With metadata
                'methodologies': List[str],
                'outcomes': str,
                'lecture_mentions': List[str]
            }
        ]
    }
}
```

### TR-2: Inline Expansion Component
- Streamlit expandable component for each topic
- Fetches content from knowledge base on expansion
- Caches expanded content to avoid re-fetching
- "Learn more" button submits full query to bot

### TR-3: Card Rendering System
- Three separate card components (Related, Teaching, Portfolio)
- Cards appear below bot response
- Responsive layout (stacks on mobile)
- Visual hierarchy: Related > Teaching > Portfolio

### TR-4: Knowledge Base Enhancements
- Add metadata to lecture segments: teaching_concepts, portfolio_mentions
- Create teaching concepts index in S3
- Create portfolio-lecture cross-reference index
- Update sync process to include new metadata

## Non-Functional Requirements

### NFR-1: Performance
- Cards must render within 500ms of bot response
- Inline expansion must load within 1 second
- No impact on bot response time (async card generation)

### NFR-2: Usability
- Cards must not overwhelm the interface (max 3-5 items per card)
- Clear visual distinction between card types
- Intuitive expand/collapse interactions
- Mobile-friendly layout

### NFR-3: Maintainability
- Teaching concepts taxonomy stored in config file (easy to update)
- Portfolio metadata stored in JSON (easy to edit)
- Card generation logic separated from bot logic

## Out of Scope (Future Enhancements)
- Personalized learning paths based on student history
- Progress tracking (which concepts explored)
- Difficulty-based filtering (beginner/advanced)
- Interactive concept map visualization
- Student-generated concept connections

## Dependencies
- Existing affinity map system
- Bedrock Knowledge Base
- Portfolio image system (needs metadata enhancement)
- Streamlit UI framework

## Success Metrics
- Students explore at least 2 related concepts per session
- 70%+ of students use inline expansion vs. submitting new queries
- Portfolio examples viewed when relevant (>50% click-through)
- Reduced repetitive questions about the same concepts

## Open Questions
1. **Portfolio Image Tagging Process**: What's the best workflow for tagging 208 images?
   - Manual tagging with UI tool?
   - Semi-automated with Claude analyzing images + descriptions?
   - Batch tagging by project with manual review?

2. **Teaching Concepts Taxonomy**: Should this be:
   - Manually curated by instructor?
   - Extracted from syllabus/course materials?
   - Generated by analyzing lecture content?

3. **Lecture-Portfolio Cross-Reference**: How to identify mentions?
   - Text search for project names in transcripts?
   - Claude analysis of lecture segments?
   - Manual annotation?

4. **Card Priority**: If all three card types are relevant, should we:
   - Always show all three?
   - Show only the most relevant one?
   - Let user toggle which cards to see?
