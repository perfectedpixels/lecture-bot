# Contextual Learning Cards - Design Document

## Architecture Overview

```
┌─────────────────────────────────────────────────────────────────┐
│                         User Query                              │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    PersonaBot.query()                           │
│  1. Safety check                                                │
│  2. Retrieve from Knowledge Base                                │
│  3. Get relevant concepts (affinity map)                        │
│  4. Generate answer                                             │
│  5. NEW: Generate learning cards                                │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│              LearningCardGenerator (NEW)                        │
│  - analyze_related_concepts()                                   │
│  - identify_teaching_concepts()                                 │
│  - find_portfolio_examples()                                    │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Enhanced Response                            │
│  {                                                              │
│    answer, sources, relevant_concepts,                          │
│    learning_cards: {                                            │
│      related_concepts: [...],                                   │
│      teaching_concepts: [...],                                  │
│      portfolio_examples: [...]                                  │
│    }                                                            │
│  }                                                              │
└────────────────────────┬────────────────────────────────────────┘
                         │
                         ▼
┌─────────────────────────────────────────────────────────────────┐
│                  Streamlit UI Rendering                         │
│  - Display bot answer                                           │
│  - Render 3 card types                                          │
│  - Handle inline expansion                                      │
│  - Manage "Learn more" actions                                  │
└─────────────────────────────────────────────────────────────────┘
```

## Component Design

### 1. LearningCardGenerator Class

**Location:** `src/learning_card_generator.py`

**Purpose:** Generate contextual learning cards based on bot response and query context

**Dependencies:**
- Affinity map (concept clusters)
- Teaching concepts taxonomy
- Portfolio metadata
- Knowledge Base (for inline expansion content)

**Key Methods:**

```python
class LearningCardGenerator:
    def __init__(self, 
                 affinity_map_path: str,
                 teaching_concepts_path: str,
                 portfolio_metadata_path: str,
                 bedrock_client,
                 knowledge_base_id: str):
        """Initialize with required data sources"""
        
    def generate_cards(self, 
                      query: str,
                      answer: str,
                      relevant_concepts: List[str],
                      sources: List[str]) -> Dict:
        """
        Generate all three card types
        Returns: {
            'related_concepts': [...],
            'teaching_concepts': [...],
            'portfolio_examples': [...]
        }
        """
        
    def analyze_related_concepts(self, 
                                relevant_concepts: List[str],
                                query: str) -> List[Dict]:
        """
        Find 3-5 related concepts from affinity map
        Returns concepts that:
        - Are in same cluster as relevant_concepts
        - Lead to deeper understanding
        - Haven't been shown in this session
        """
        
    def identify_teaching_concepts(self,
                                  query: str,
                                  answer: str,
                                  relevant_concepts: List[str]) -> List[Dict]:
        """
        Map to 3-5 high-level teaching concepts
        Uses taxonomy + Claude to identify which concepts apply
        """
        
    def find_portfolio_examples(self,
                               query: str,
                               answer: str,
                               relevant_concepts: List[str],
                               sources: List[str]) -> List[Dict]:
        """
        Find 1-3 relevant portfolio projects
        Matches on:
        - Concept tags
        - Teaching concepts
        - Lecture mentions (cross-reference)
        """
        
    def get_inline_content(self,
                          concept_name: str,
                          concept_type: str) -> str:
        """
        Fetch content for inline expansion
        Queries Knowledge Base for concept-specific segments
        """
```

### 2. Teaching Concepts Taxonomy

**Location:** `data/teaching_concepts.json`

**Structure:**
```json
{
  "Information Architecture": {
    "definition": "The structural design of information environments to support usability and findability",
    "key_principles": [
      "Organization schemes (hierarchical, sequential, matrix)",
      "Labeling systems",
      "Navigation systems",
      "Search systems"
    ],
    "related_affinity_clusters": ["ia_fundamentals", "navigation_design"],
    "keywords": ["site map", "navigation", "taxonomy", "content structure", "findability"],
    "example_deliverables": ["site maps", "navigation diagrams", "content models"]
  },
  "User Research Methods": {
    "definition": "Systematic investigation of users and their needs to inform design decisions",
    "key_principles": [
      "Qualitative vs quantitative methods",
      "Generative vs evaluative research",
      "Contextual inquiry",
      "Triangulation of data"
    ],
    "related_affinity_clusters": ["research_methods", "user_testing"],
    "keywords": ["interviews", "surveys", "observation", "usability testing", "personas"],
    "example_deliverables": ["research plans", "interview guides", "personas", "journey maps"]
  }
  // ... 18 more concepts
}
```

### 3. Portfolio Metadata Enhancement

**Location:** `data/portfolio_image_metadata.json`

**Structure:** (Generated by tagging script)
```json
{
  "indeed": {
    "title": "Indeed Job Seeker Redesign",
    "summary": {
      "primary_concepts": ["User Research Methods", "Interface Design"],
      "methodologies_used": ["user interviews", "A/B testing"],
      "key_outcomes": "250M users, +$350M revenue",
      "lecture_mentions": [
        {
          "lecture_id": "week_3_user_research",
          "context": "Discussed how we conducted 50+ user interviews",
          "timestamp": "15:30"
        }
      ]
    },
    "images": [
      {
        "filename": "indeed_research_1.jpg",
        "path": "portfolio_images/indeed/indeed_research_1.jpg",
        "s3_url": "https://...",
        "concept_tags": ["user research", "persona definition"],
        "phase": "research",
        "methodology": "user interviews",
        "description": "User interview session with job seekers",
        "teaching_concepts": ["User Research Methods", "Persona Definition"]
      }
    ]
  }
}
```

### 4. Enhanced Bot Response Structure

**Modified:** `src/persona_bot_safe.py`

**Changes to `query()` method:**
```python
def query(self, question: str, max_results: int = 5, use_persona: bool = True) -> dict:
    # ... existing code ...
    
    # NEW: Generate learning cards
    if self.card_generator:
        learning_cards = self.card_generator.generate_cards(
            query=question,
            answer=answer,
            relevant_concepts=relevant_concepts,
            sources=[r['location']['s3Location']['uri'] for r in response['retrievalResults']]
        )
    else:
        learning_cards = None
    
    return {
        'question': question,
        'answer': answer,
        'sources': [r['location']['s3Location']['uri'] for r in response['retrievalResults']],
        'relevant_concepts': relevant_concepts,
        'context': context,
        'safety_triggered': False,
        'learning_cards': learning_cards  # NEW
    }
```

### 5. UI Components

**Location:** `app/streamlit_app_redesign.py`

**New Components:**

#### A. Card Container
```python
def render_learning_cards(cards: Dict, chat_idx: int):
    """Render all three card types"""
    if not cards:
        return
    
    # Card 1: Related Concepts (from affinity map)
    if cards.get('related_concepts'):
        render_related_concepts_card(cards['related_concepts'], chat_idx)
    
    # Card 2: Teaching Concepts (high-level)
    if cards.get('teaching_concepts'):
        render_teaching_concepts_card(cards['teaching_concepts'], chat_idx)
    
    # Card 3: Portfolio Examples
    if cards.get('portfolio_examples'):
        render_portfolio_card(cards['portfolio_examples'], chat_idx)
```

#### B. Related Concepts Card
```python
def render_related_concepts_card(concepts: List[Dict], chat_idx: int):
    """
    Card showing 3-5 related concepts from affinity map
    Each concept is expandable inline
    """
    st.markdown("### 🎓 Related Concepts")
    
    for idx, concept in enumerate(concepts):
        with st.expander(f"▶ {concept['name']}", expanded=False):
            # Show preview
            st.markdown(concept['preview'])
            
            # Inline content (lazy loaded)
            if st.button("Learn more", key=f"related_{chat_idx}_{idx}"):
                # Fetch and display full content
                content = fetch_concept_content(concept['segment_ids'])
                st.markdown(content)
                
                # Option to submit as full query
                if st.button("Ask Professor Levine about this", key=f"ask_{chat_idx}_{idx}"):
                    st.session_state.pending_question = f"Can you explain {concept['name']} in detail?"
                    st.rerun()
```

#### C. Teaching Concepts Card
```python
def render_teaching_concepts_card(concepts: List[Dict], chat_idx: int):
    """
    Card showing 3-5 high-level teaching concepts
    Each concept shows definition + key principles
    """
    st.markdown("### 📚 Core Teaching Concepts")
    
    for idx, concept in enumerate(concepts):
        with st.expander(f"▶ {concept['name']}", expanded=False):
            st.markdown(f"**Definition:** {concept['definition']}")
            
            st.markdown("**Key Principles:**")
            for principle in concept['key_principles']:
                st.markdown(f"- {principle}")
            
            if st.button("Explore this concept", key=f"teaching_{chat_idx}_{idx}"):
                st.session_state.pending_question = f"Tell me more about {concept['name']} with examples from your experience"
                st.rerun()
```

#### D. Portfolio Examples Card
```python
def render_portfolio_card(examples: List[Dict], chat_idx: int):
    """
    Card showing 1-3 portfolio projects with images
    Each project is expandable with details
    """
    st.markdown("### 💼 See It in Practice")
    
    for idx, project in enumerate(examples):
        with st.expander(f"▶ {project['project_name']}", expanded=False):
            st.markdown(project['description'])
            
            # Show images
            if project.get('images'):
                cols = st.columns(min(len(project['images']), 3))
                for img_idx, img in enumerate(project['images'][:3]):
                    with cols[img_idx]:
                        st.image(img['s3_url'], caption=img['description'], use_container_width=True)
            
            # Show methodologies and outcomes
            st.markdown(f"**Methodologies:** {', '.join(project['methodologies'])}")
            st.markdown(f"**Outcomes:** {project['outcomes']}")
            
            # Link to lecture mentions
            if project.get('lecture_mentions'):
                st.markdown("**Mentioned in lectures:**")
                for mention in project['lecture_mentions']:
                    st.caption(f"- {mention}")
            
            if st.button("Learn more about this project", key=f"portfolio_{chat_idx}_{idx}"):
                st.session_state.pending_question = f"Tell me more about your work on {project['project_name']}"
                st.rerun()
```

## Data Flow

### Card Generation Flow

```
1. User asks question
   ↓
2. Bot generates answer + gets relevant_concepts from affinity map
   ↓
3. LearningCardGenerator.generate_cards() called
   ↓
4. Three parallel processes:
   
   A. analyze_related_concepts()
      - Look at relevant_concepts
      - Find concepts in same/related clusters
      - Filter out already discussed
      - Return 3-5 concepts with previews
   
   B. identify_teaching_concepts()
      - Analyze query + answer
      - Match to teaching concepts taxonomy
      - Use Claude to determine relevance
      - Return 3-5 teaching concepts with definitions
   
   C. find_portfolio_examples()
      - Match concept_tags to query/answer
      - Check lecture_mentions in sources
      - Filter by teaching_concepts
      - Return 1-3 projects with images
   ↓
5. Cards returned in response
   ↓
6. UI renders three card types
   ↓
7. User clicks to expand inline
   ↓
8. Content fetched from Knowledge Base (lazy load)
   ↓
9. User clicks "Learn more" → submits new query
```

### Inline Expansion Flow

```
1. User clicks concept in card
   ↓
2. Expander opens (Streamlit native)
   ↓
3. Preview content shown (already in card data)
   ↓
4. User clicks "Learn more" button
   ↓
5. get_inline_content() called
   ↓
6. Query Knowledge Base for concept-specific segments
   ↓
7. Content displayed inline
   ↓
8. "Ask Professor Levine" button appears
   ↓
9. Click → submits full query to bot
```

## CSS Styling

**Card Styles:**
```css
/* Card container */
.learning-card {
    background: rgba(255, 255, 255, 0.05);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 12px;
    padding: 20px;
    margin: 15px 0;
    backdrop-filter: blur(10px);
}

/* Card header */
.learning-card h3 {
    color: white;
    font-size: 18px;
    margin-bottom: 15px;
    display: flex;
    align-items: center;
    gap: 10px;
}

/* Concept item */
.concept-item {
    background: rgba(255, 255, 255, 0.03);
    border-left: 3px solid #7B2FFF;
    padding: 12px;
    margin: 8px 0;
    border-radius: 6px;
    cursor: pointer;
    transition: all 0.2s;
}

.concept-item:hover {
    background: rgba(255, 255, 255, 0.08);
    border-left-color: #9D4EDD;
}

/* Portfolio project */
.portfolio-project {
    background: rgba(255, 255, 255, 0.03);
    border: 1px solid rgba(255, 255, 255, 0.1);
    border-radius: 8px;
    padding: 15px;
    margin: 10px 0;
}

.portfolio-project img {
    border-radius: 6px;
    margin: 10px 0;
}
```

## Performance Considerations

### Optimization Strategies

1. **Lazy Loading**
   - Card data generated immediately (fast)
   - Inline content fetched only on expansion (lazy)
   - Images loaded on-demand

2. **Caching**
   - Cache teaching concepts taxonomy (static)
   - Cache portfolio metadata (rarely changes)
   - Cache expanded content per session

3. **Async Generation**
   - Generate cards after answer is displayed
   - Don't block bot response
   - Show loading state for cards

4. **Batch Queries**
   - Fetch multiple concept contents in one KB query
   - Batch image metadata lookups

### Performance Targets

- Card generation: < 500ms
- Inline expansion: < 1s
- No impact on bot response time

## Error Handling

### Graceful Degradation

```python
def generate_cards(self, ...):
    try:
        related = self.analyze_related_concepts(...)
    except Exception as e:
        logger.error(f"Failed to generate related concepts: {e}")
        related = []
    
    try:
        teaching = self.identify_teaching_concepts(...)
    except Exception as e:
        logger.error(f"Failed to generate teaching concepts: {e}")
        teaching = []
    
    try:
        portfolio = self.find_portfolio_examples(...)
    except Exception as e:
        logger.error(f"Failed to generate portfolio examples: {e}")
        portfolio = []
    
    # Return whatever we successfully generated
    return {
        'related_concepts': related,
        'teaching_concepts': teaching,
        'portfolio_examples': portfolio
    }
```

### Fallback Behavior

- If card generation fails → show no cards (don't break chat)
- If inline expansion fails → show error message, allow retry
- If images fail to load → show placeholder or text-only

## Testing Strategy

### Unit Tests

1. **LearningCardGenerator**
   - Test concept matching logic
   - Test teaching concept identification
   - Test portfolio filtering
   - Mock Bedrock/KB calls

2. **Data Loading**
   - Test affinity map parsing
   - Test teaching concepts loading
   - Test portfolio metadata loading

### Integration Tests

1. **End-to-End Flow**
   - Submit query → verify cards generated
   - Expand concept → verify content loaded
   - Click "Learn more" → verify new query submitted

2. **Edge Cases**
   - No relevant concepts found
   - No portfolio examples match
   - Affinity map missing
   - Portfolio metadata missing

### Manual Testing

1. **Content Quality**
   - Are suggested concepts relevant?
   - Are teaching concepts appropriate?
   - Are portfolio examples well-matched?

2. **UX Testing**
   - Is inline expansion intuitive?
   - Are cards overwhelming or helpful?
   - Do students use the cards?

## Deployment Plan

### Phase 1: Data Preparation
1. Run portfolio tagging script
2. Review and refine tags
3. Create teaching concepts taxonomy
4. Upload metadata to S3

### Phase 2: Backend Implementation
1. Create LearningCardGenerator class
2. Enhance PersonaBot.query()
3. Add inline content fetching
4. Unit test all components

### Phase 3: UI Implementation
1. Create card rendering components
2. Add inline expansion logic
3. Style cards for UW purple theme
4. Test on desktop and mobile

### Phase 4: Integration & Testing
1. Connect backend to UI
2. End-to-end testing
3. Performance optimization
4. User acceptance testing

### Phase 5: Deployment
1. Deploy to EC2
2. Monitor performance
3. Gather user feedback
4. Iterate based on usage

## Monitoring & Metrics

### Key Metrics

1. **Usage Metrics**
   - % of responses that show cards
   - % of students who expand concepts
   - % of students who click "Learn more"
   - Most expanded concepts

2. **Performance Metrics**
   - Card generation time
   - Inline expansion time
   - Cache hit rate

3. **Quality Metrics**
   - Relevance of suggested concepts (user feedback)
   - Portfolio example match quality
   - Teaching concept accuracy

### Logging

```python
logger.info(f"Generated cards for query: {query}")
logger.info(f"  Related concepts: {len(related)}")
logger.info(f"  Teaching concepts: {len(teaching)}")
logger.info(f"  Portfolio examples: {len(portfolio)}")
logger.info(f"  Generation time: {elapsed}ms")
```

## Future Enhancements

1. **Personalization**
   - Track which concepts student has explored
   - Suggest concepts based on knowledge gaps
   - Adaptive difficulty (beginner → advanced)

2. **Interactive Concept Map**
   - Visual graph of concept relationships
   - Click to explore connections
   - Highlight learning path

3. **Progress Tracking**
   - Mark concepts as "learned"
   - Show completion percentage
   - Suggest next topics

4. **Collaborative Learning**
   - See what other students explored
   - Popular concepts this week
   - Peer recommendations

5. **Multi-Modal Content**
   - Video clips from lectures
   - Interactive prototypes
   - Animated explanations

## Open Questions

1. **Card Priority**: If all three cards are relevant, should we show all three or prioritize?
   - **Recommendation**: Show all three, but in order: Related → Teaching → Portfolio

2. **Session Persistence**: Should expanded content persist across page refreshes?
   - **Recommendation**: No, keep session state clean. Re-expand if needed.

3. **Mobile Experience**: How should cards render on mobile?
   - **Recommendation**: Stack vertically, collapse by default, one card open at a time

4. **Lecture-Portfolio Cross-Reference**: Best method to identify mentions?
   - **Recommendation**: Combination of text search + Claude analysis (see implementation tasks)
