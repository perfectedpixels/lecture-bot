# Portfolio Image Tagging Guide

## Overview
This guide explains how to tag your 208 portfolio images with concept metadata so the learning cards can show relevant examples.

## Tagging Strategy: Semi-Automated

We use a **two-phase approach**:
1. **Phase 1**: Claude analyzes each project and suggests tags (automated)
2. **Phase 2**: You review and refine the tags (manual)

This balances efficiency with accuracy.

## Phase 1: Automated Tagging

### Step 1: Run the Tagging Script

```bash
python scripts/tag_portfolio_images.py tag
```

**What it does:**
- Analyzes each of your 21 portfolio projects
- Reads project descriptions from `perfectpixels_complete_portfolio.txt`
- Uses Claude to suggest:
  - **Concept tags** (e.g., "user research", "information architecture")
  - **Phase** (research, design, testing, etc.)
  - **Methodology** (contextual inquiry, usability testing, etc.)
  - **Description** (what the image shows)
  - **Teaching concepts** (maps to high-level concepts like "User Research Methods")

**Output:** `data/portfolio_image_metadata.json`

**Time estimate:** ~5-10 minutes for all 208 images

### Example Output

```json
{
  "indeed": {
    "title": "Indeed Job Seeker Redesign",
    "summary": {
      "primary_concepts": ["User Research Methods", "Interface Design", "Data-Driven Design"],
      "methodologies_used": ["user interviews", "A/B testing", "analytics"],
      "key_outcomes": "250M users, +$350M revenue"
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

## Phase 2: Manual Review & Refinement

### Step 2: Review Tags

```bash
python scripts/tag_portfolio_images.py review
```

**What it does:**
- Shows you each project and its images
- Displays Claude's suggested tags
- Lets you edit:
  - Description
  - Concept tags
  - Phase
  - Methodology

**Interactive prompts:**
```
Project: Indeed Job Seeker Redesign
Primary Concepts: User Research Methods, Interface Design
Images: 11

Review images? (y/n/q to quit): y

  Image: indeed_research_1.jpg
  Description: User interview session with job seekers
  Concepts: user research, persona definition
  Phase: research
  Methodology: user interviews
  
  Edit? (y/n): y
  New description [User interview session with job seekers]: 
  New concepts [user research, persona definition]: user research, contextual inquiry
  New phase [research]: 
```

**Time estimate:** ~30-60 minutes to review all images

## Metadata Schema

Each image gets tagged with:

### 1. Concept Tags (specific)
Examples: "user research", "wireframing", "journey mapping", "A/B testing"
- **Purpose**: Match to specific activities/deliverables
- **Used for**: Filtering images by what they show

### 2. Phase (project stage)
Options: research, ideation, design, prototyping, testing, implementation, analysis
- **Purpose**: Show where in the process this fits
- **Used for**: Teaching project lifecycle

### 3. Methodology (how it was done)
Examples: "contextual inquiry", "usability testing", "design thinking"
- **Purpose**: Show the method used
- **Used for**: Teaching research/design methods

### 4. Description (what you see)
Example: "User interview session with job seekers in their home office"
- **Purpose**: Explain the image
- **Used for**: Image captions and context

### 5. Teaching Concepts (high-level)
Examples: "User Research Methods", "Information Architecture", "Usability Testing"
- **Purpose**: Map to course curriculum
- **Used for**: Learning card matching

## Teaching Concepts Taxonomy

The system maps specific tags to these high-level concepts:

- **Information Architecture** - site maps, navigation, content structure
- **Branding & Identity** - logos, style guides, brand systems
- **Simplification & Clarity** - before/after, complexity reduction
- **Interface Design** - screens, layouts, components
- **Usability Testing** - test sessions, findings, iterations
- **Persona Definition** - user profiles, empathy maps
- **AI Ethics** - ethical considerations, bias mitigation
- **User Research Methods** - interviews, surveys, observations
- **Design Systems** - component libraries, patterns
- **Workflow Automation** - process diagrams, automation
- **Visual Design** - aesthetics, typography, color
- **Interaction Design** - flows, animations, micro-interactions
- **Content Strategy** - content models, voice/tone
- **Accessibility** - WCAG compliance, inclusive design
- **Design Thinking** - ideation, prototyping, iteration
- **Agile/Lean UX** - sprints, MVPs, continuous delivery
- **Data-Driven Design** - analytics, metrics, A/B tests
- **Prototyping** - wireframes, mockups, interactive prototypes
- **Journey Mapping** - customer journeys, service blueprints
- **Service Design** - touchpoints, ecosystems

## Best Practices

### DO:
✅ Be specific with concept tags ("user interviews" not just "research")
✅ Include multiple tags if image shows multiple concepts
✅ Use consistent terminology across similar images
✅ Add context in descriptions (who, what, where, why)
✅ Map to teaching concepts that match your curriculum

### DON'T:
❌ Over-tag (max 3-5 concept tags per image)
❌ Use vague tags ("design" - be more specific)
❌ Skip the description (it provides important context)
❌ Forget to map to teaching concepts
❌ Use inconsistent phase names

## Integration with Learning Cards

Once tagged, images will appear in "See It in Practice" cards when:

1. **Concept match**: Student asks about a concept that matches image tags
2. **Lecture mention**: Project is mentioned in the lecture being discussed
3. **Teaching concept**: High-level concept matches current topic

Example:
```
Student asks: "How do you conduct user research?"

Card shows:
┌─────────────────────────────────────┐
│ 🎯 See It in Practice               │
├─────────────────────────────────────┤
│ Indeed Job Seeker Redesign          │
│ [Image: User interview session]     │
│                                     │
│ Methodology: Contextual Inquiry     │
│ Outcome: 250M users, +$350M revenue │
│                                     │
│ → Learn more about this project     │
└─────────────────────────────────────┘
```

## Troubleshooting

### Claude suggests wrong tags
- **Solution**: Use the review tool to correct them
- **Prevention**: Improve project descriptions in portfolio content

### Missing teaching concept mappings
- **Solution**: Edit `_map_to_teaching_concepts()` in the script
- **Add**: New mappings for your specific terminology

### Images not showing in cards
- **Check**: Metadata file exists and is valid JSON
- **Check**: S3 URLs are accessible
- **Check**: Concept tags match what's in affinity map

## Next Steps

After tagging:
1. Upload metadata to S3: `aws s3 cp data/portfolio_image_metadata.json s3://BUCKET/metadata/`
2. Update bot to use metadata (see design.md)
3. Test learning cards with various queries
4. Refine tags based on relevance

## Maintenance

**When adding new projects:**
1. Add images to `data/portfolio_images/`
2. Update `portfolio_image_map.json`
3. Run tagging script on new project
4. Review and refine tags
5. Upload updated metadata to S3

**When updating curriculum:**
1. Add new teaching concepts to taxonomy
2. Update concept mappings in script
3. Re-tag relevant images
4. Upload updated metadata
