---
inclusion: auto
---

# Lecture Bot Integration Guide

This steering document provides context for integrating the Jason Levine Lecture Bot into the portfolio application.

## Project Context

This is a lecture bot system that creates a virtual persona based on Jason Levine's teaching lectures. The bot can answer questions about lecture content and Jason's professional experience as if it were Jason himself.

## Current State (March 2026)

### Knowledge Base Configuration (Current - Shared KB)
- **AWS Account**: `582234715800` (personal)
- **Knowledge Base ID**: `HHYCUJH32J`
- **Region**: `us-east-1`
- **S3 Bucket**: `perfectpixels-kb-docs`
- **S3 Prefix**: `kb-clean/v1/`
- **Vector Store**: S3 Vectors (non-filterable metadata index)
- **IAM User**: `perfectpixels-bot`
- **Model**: `us.anthropic.claude-sonnet-4-20250514-v1:0` (Claude Sonnet 4)

### OLD KBs (DECOMMISSIONED)
- KB `SSIRB24COT` — replaced by `HHYCUJH32J` (had filterable metadata 2048-byte limit)
- KB `1TTBVE6MG2` — original, account `427791004700`
- IAM user `video-annotator` - deactivate credentials

### What's Indexed
1. **38 Lecture Transcripts** - Cleaned, semantically chunked (400 tokens/chunk, 50 overlap)
2. **CV** - Jason's professional work history
3. **Portfolio** - Perfect Pixels portfolio with project details

### Metadata Structure
Each chunk includes:
- `topics`: AI, design, research, IoT, professional-experience
- `concepts`: UX, personas, user-journey, heuristics, artificial-intelligence, branding
- `companies`: Amazon, Indeed, AWS, Virgin, Microsoft, TraderJoes, Pulse, PerfectPixels
- `portfolio_examples`: Indeed, AWS, Amazon, Virgin, Microsoft, TraderJoes
- `source`: Original filename
- `doc_type`: lecture, cv, or portfolio

## AWS Credentials

### Required Permissions
The AWS credentials need these permissions:
- **Bedrock**: `InvokeModel`, `InvokeModelWithResponseStream`, `bedrock:Retrieve`
- **S3**: Read access to `perfectpixels-kb-docs` bucket
- **Region**: `us-east-1`

### Environment Variables Required
```bash
AWS_ACCESS_KEY_ID=<from .env>
AWS_SECRET_ACCESS_KEY=<from .env>
AWS_REGION=us-east-1
BEDROCK_KNOWLEDGE_BASE_ID=HHYCUJH32J
BEDROCK_MODEL_ID=us.anthropic.claude-sonnet-4-20250514-v1:0
```

**Note**: Credentials are stored in `.env`. Do not commit credentials to git.

## Bot Files to Use

### Recommended: Persona Bot with Sonnet 4
```python
from src.persona_bot_fast import FastPersonaBot

bot = FastPersonaBot(
    knowledge_base_id="HHYCUJH32J",
    persona_name="Professor Levine"
)

result = bot.query("What is design thinking?")
print(result['answer'])
```

### Alternative: Enhanced Bot
```python
from src.persona_bot_enhanced import EnhancedPersonaBot

bot = EnhancedPersonaBot(
    knowledge_base_id="HHYCUJH32J",
    persona_name="Professor Levine"
)
```

### With Caching (Recommended)
```python
from src.response_cache import CachedPersonaBot
from src.persona_bot_fast import FastPersonaBot

bot = FastPersonaBot("HHYCUJH32J")
cached_bot = CachedPersonaBot(bot)

# First call: 1-2s
result = cached_bot.query("Explain user personas")

# Repeated call: 0.3s
result = cached_bot.query("Explain user personas")
```

## Important Bot Behaviors

### 1. No Meta-Phrases
The bot has been updated to NOT say "Speaking as Jason Levine" or similar phrases. Responses start directly with the answer.

If you see these phrases, the bot files need to be updated. All three bot files now include:
- Stronger prompt instructions
- Post-processing with `_clean_response()` method

### 2. Query Expansion
The bot automatically expands queries for better retrieval:
- Detects domain (healthcare, design, research)
- Adds relevant terms
- No LLM call needed (keyword-based)
- Speed is achieved through improved chunking and keyword associations, not model downgrade

### 3. Response Format
```python
{
    'question': str,      # Original question
    'answer': str,        # Generated answer (cleaned)
    'sources': List[str], # S3 URIs of source chunks
    'context': str,       # Retrieved context used
    'learning_cards': {   # Follow-up suggestions (if card generator available)
        'related_concepts': [...],
        'teaching_concepts': [...],
        'portfolio_examples': [...]
    }
}
```

## Testing Queries

### Lecture Content
- "Explain user personas"
- "What is design thinking?"
- "Tell me about AI frameworks"
- "What are heuristics?"
- "Explain usability studies"

### Professional Experience
- "What is my professional experience?"
- "Tell me about my work at Amazon"
- "What projects did I do at Indeed?"
- "Show me examples from my portfolio"

### Portfolio Examples
- "Tell me about the Trader Joe's project"
- "What AWS work have I done?"
- "Show me Virgin projects"

## Performance Expectations

### Speed (with Sonnet 4)
- First query: ~1-2 seconds (with 3 results)
- Cached query: 0.3-0.5 seconds
- Speed improved via semantic chunking and keyword associations
- Reduced to 3 results (from 6) for faster retrieval

### Speed Optimization Tips
1. **Semantic chunking**: 400 tokens/chunk with 50 overlap for precise retrieval
2. **Keyword associations**: Improved metadata tagging reduces irrelevant results
3. **Reduce results**: Use `max_results=3` instead of default 6
4. **Enable caching**: Wrap bot with `ResponseCache`
5. **Shorter responses**: Reduced max_tokens to 1500

Example for maximum speed:
```python
from src.persona_bot_fast import FastPersonaBot
from src.response_cache import CachedPersonaBot

bot = FastPersonaBot("HHYCUJH32J")
cached_bot = CachedPersonaBot(bot)

# Fast query with fewer results
result = cached_bot.query("What is design thinking?", max_results=3)
```

### Accuracy
- 50-80% better than original setup
- Semantic chunking improves context matching
- Metadata enables better filtering
- Sonnet 4 provides higher accuracy than previous models

### Cost
- Sonnet 4: ~$3 per 1M input tokens, ~$15 per 1M output tokens
- Caching: Free for repeated queries

## Common Issues

### Empty Results
- **Cause**: Knowledge Base not synced or wrong KB ID
- **Fix**: Verify `BEDROCK_KNOWLEDGE_BASE_ID=HHYCUJH32J` and data source synced

### Slow Responses
- **Cause**: Too many retrieval results or missing caching
- **Fix**: Use `max_results=3` and wrap with `ResponseCache`

### "Speaking as" Appears
- **Cause**: Old bot files
- **Fix**: Copy latest bot files from lecture bot repo

### Wrong Information
- **Cause**: Query too vague or content doesn't exist
- **Fix**: Make query more specific, add context like "In your lectures about..."

## Integration Checklist

When integrating into portfolio app:

- [ ] Copy bot files: `persona_bot_fast.py`, `improved_retrieval.py`, `response_cache.py`
- [ ] Create `.env` with AWS credentials
- [ ] Install dependencies: `boto3`, `python-dotenv`
- [ ] Test basic query: "What is design thinking?"
- [ ] Test professional query: "What is my work experience?"
- [ ] Verify no "Speaking as" phrases
- [ ] Enable caching for repeated queries
- [ ] Add error handling for API failures

## File Locations in This Repo

- Bot files: `src/persona_bot*.py`
- Helper files: `src/improved_retrieval.py`, `src/response_cache.py`
- Scripts: `scripts/clean_rebuild.py`, `scripts/add_cv_portfolio.py`
- Docs: `KB_REBUILD_SUMMARY.md`, `QUICK_CREDENTIALS_SETUP.md`
- Example: `.env.example`

## Key Differences from Previous Setup

### What Changed
1. **Migrated to personal AWS account**: `582234715800` (from `427791004700`)
2. **New Knowledge Base**: `HHYCUJH32J` (from `SSIRB24COT`, originally `1TTBVE6MG2`)
3. **New S3 bucket**: `perfectpixels-kb-docs` (from `lecture-transcripts-427791004700`)
4. **New vector store**: S3 Vectors with non-filterable metadata index (from OpenSearch Serverless - 90% cheaper)
5. **Upgraded model**: Claude Sonnet 4 (from Claude 3 Sonnet legacy)
6. **New IAM user**: `perfectpixels-bot` (from `video-annotator`)
7. **Clean chunking pipeline**: `kb-clean/v1/` prefix with indexed docs, 0 failures
8. **No meta-phrases**: Responses cleaned of "Speaking as..."
9. **Learning cards**: `FastPersonaBot` now generates follow-up suggestions via `LearningCardGenerator`

### What Stayed the Same
- Region: `us-east-1`
- Bot interface: Same `query()` method signature
- Response format: Same dictionary structure

## Support

If you encounter issues:
1. Check `KB_REBUILD_SUMMARY.md` for detailed setup info
2. Review `QUICK_CREDENTIALS_SETUP.md` for AWS credential issues
3. See `SPEED_OPTIMIZATION_GUIDE.md` for performance tuning
4. Check `.env.example` for required environment variables

## Summary for Portfolio App Integration

**Copy these files**:
- `src/persona_bot_fast.py`
- `src/improved_retrieval.py`
- `src/response_cache.py`
- `.env` (with credentials)

**Use this code**:
```python
from src.persona_bot_fast import FastPersonaBot

bot = FastPersonaBot(
    knowledge_base_id="HHYCUJH32J",
    persona_name="Professor Levine"
)

result = bot.query("Your question here")
answer = result['answer']  # Clean, no meta-phrases
```

**Test with**:
- "Explain user personas"
- "What is my professional experience?"
- "Tell me about the Trader Joe's project"

That's it! The bot is ready to integrate.
