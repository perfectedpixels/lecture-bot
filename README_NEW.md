# Lecture Bot with Contextual Learning Cards

AI-powered teaching assistant for UX/Design courses with intelligent learning card suggestions.

## Features

- 🤖 **AI Teaching Assistant** - Responds as Professor Levine using course lecture content
- 💡 **Contextual Learning Cards** - Three types of intelligent suggestions:
  - 📚 Core Teaching Concepts (with definitions and principles)
  - 🔗 Related Concepts (from affinity map clustering)
  - 🎨 See It in Practice (portfolio examples with images)
- ⏳ **Skeleton Loading** - Google-style shimmer animation while generating
- 🎙️ **Voice Support** - Text-to-speech responses with ElevenLabs
- 🎨 **UW Purple Theme** - Beautiful gradient design

## Live Demo

🚀 **[Try it here](https://YOUR-APP.streamlit.app)** (coming soon)

## Tech Stack

- **Frontend**: Streamlit
- **AI**: AWS Bedrock (Claude 3 Sonnet)
- **Voice**: ElevenLabs
- **Storage**: AWS S3
- **Knowledge Base**: AWS Bedrock Knowledge Base

## Quick Start

### For Students

Just visit the live URL and start asking questions about the course!

### For Developers

1. Clone the repo
2. Install dependencies: `pip install -r requirements.txt`
3. Copy `.streamlit/secrets.toml.example` to `.streamlit/secrets.toml`
4. Add your AWS credentials and Knowledge Base ID
5. Run: `streamlit run app/streamlit_app_redesign.py`

## Project Structure

```
├── app/
│   ├── streamlit_app_redesign.py  # Main app with learning cards
│   └── streamlit_app_simple.py    # Simple version
├── src/
│   ├── persona_bot_safe.py        # AI bot with safety rules
│   ├── learning_card_generator.py # Card generation engine
│   └── voice_generator.py         # Text-to-speech
├── data/
│   ├── teaching_concepts.json     # 20 teaching concepts
│   ├── portfolio_image_metadata.json  # 208 tagged images
│   └── affinity_map.json          # Concept clusters
└── scripts/
    ├── generate_affinity_map.py   # Create concept clusters
    ├── tag_portfolio_images.py    # Tag images with concepts
    └── cross_reference_lectures.py # Link portfolio to lectures
```

## Features in Detail

### Contextual Learning Cards

After each bot response, students see three types of cards:

1. **Core Teaching Concepts** - High-level concepts with:
   - Definition
   - Key principles
   - "Learn more" inline expansion
   - "Ask Professor Levine" button

2. **Related Concepts** - Topics from the same or related clusters:
   - Grouped by affinity
   - "Ask about this" buttons
   - Intelligent relevance scoring

3. **See It in Practice** - Portfolio examples:
   - Real project examples
   - Images from S3
   - Cross-referenced with lecture mentions
   - Expandable image galleries

### Data Preparation

- **208 images** tagged with concept metadata
- **20 teaching concepts** with definitions and principles
- **44 portfolio mentions** found in lecture transcripts
- **10 concept clusters** from affinity mapping

## Deployment

### Streamlit Cloud (Recommended)

1. Push to GitHub
2. Connect to Streamlit Cloud
3. Add secrets in dashboard
4. Deploy!

See `DEPLOY_STREAMLIT_CLOUD.md` for detailed instructions.

## Documentation

- `LEARNING_CARDS_IMPLEMENTATION.md` - Feature implementation details
- `FEATURES_COMPLETE.md` - All features and setup
- `DEPLOY_STREAMLIT_CLOUD.md` - Streamlit Cloud deployment
- `DEPLOYMENT_CHECKLIST.md` - Troubleshooting guide

## Credits

Created by Jason Levine for COMMLD 515/512 at University of Washington.

## License

Educational use only.
