---
inclusion: auto
---

# GitHub & Streamlit Cloud Deployment Instructions

This steering document contains all necessary instructions for storing code to GitHub and hosting through Streamlit Cloud, which is the only supported, documented deployment path for this app today.

### Note: a second, exploratory deployment path exists (not yet supported)

The repo also contains an in-progress FastAPI + React + AWS App Runner path — `api/`, `frontend/`, `Dockerfile`, `deploy-apprunner.sh` — meant to expose the bot as an HTTP API for a separate portfolio project (`ux-team-kb`). As of this writing those files are **uncommitted and exploratory/on hold**: don't treat `deploy-apprunner.sh` as a working deploy script or assume the API is live. Streamlit Cloud (below) remains the real, working deployment. See [lecture-bot-integration.md](lecture-bot-integration.md) for what the API path is intended to do once it's picked back up.

---

## GitHub Repository Management

### Initial Setup

```bash
# Initialize git (if not already done)
git init
git add .
git commit -m "Initial commit"

# Create repo on GitHub at https://github.com/new
# Then connect local to remote:
git remote add origin https://github.com/YOUR_USERNAME/lecture-bot.git
git branch -M main
git push -u origin main
```

### Daily Workflow

```bash
# Stage changes
git add .

# Commit with descriptive message
git commit -m "Description of changes"

# Push to GitHub (triggers auto-deployment)
git push origin main
```

### Essential Files to Track

- `app/streamlit_app_redesign.py` - Main application
- `requirements.txt` - Python dependencies
- `src/` - All source code modules
- `data/` - Images, JSON configs, teaching concepts
- `.streamlit/config.toml` - Streamlit configuration

### Files to Ignore (.gitignore)

```
.streamlit/secrets.toml
*.pyc
__pycache__/
.env
.DS_Store
venv/
```

---

## Streamlit Cloud Deployment

### Initial Deployment

1. Go to https://share.streamlit.io/
2. Sign in with GitHub
3. Click "New app"
4. Configure:
   - Repository: `YOUR_USERNAME/lecture-bot`
   - Branch: `main`
   - Main file: `app/streamlit_app_redesign.py`
5. Click "Deploy!"

### Secrets Configuration

**CRITICAL**: AWS credentials MUST be UPPERCASE

In Streamlit Cloud → Manage app → Settings → Secrets:

```toml
AWS_ACCESS_KEY_ID = "YOUR_AWS_ACCESS_KEY"
AWS_SECRET_ACCESS_KEY = "YOUR_AWS_SECRET_KEY"
AWS_DEFAULT_REGION = "us-east-1"

KB_ID_515 = "YOUR_KNOWLEDGE_BASE_ID"
KB_ID_512 = "YOUR_OTHER_KB_ID"  # Optional

ELEVENLABS_API_KEY = "YOUR_ELEVENLABS_KEY"  # Optional
```

### Auto-Deployment

- Every `git push` to `main` branch triggers automatic redeployment
- Takes 1-2 minutes to complete
- Check logs if deployment fails
- Manual reboot: Manage app → Reboot app

---

## Common Issues & Solutions

### "Unable to locate credentials"
- Verify AWS keys are UPPERCASE in secrets
- No quotes around values
- Restart app after adding secrets

### Images not loading
- Verify files exist in GitHub: `data/uw-background.png`, `data/uw-logo.png`
- Check app logs for path errors
- Ensure images are committed and pushed

### Import errors
- Check all dependencies in `requirements.txt`
- Verify package names and versions
- Review logs for specific missing packages

### App crashes on startup
- Check Manage app → Logs
- Common causes: missing secrets, import errors, file path issues

---

## Adding New Lecture Content

### Convert RTF Files

```bash
pip3 install striprtf
python3 scripts/convert_rtf_to_txt.py data/rtfs data/converted_lectures
```

### Upload to S3 & Sync Bedrock

1. Upload converted .txt files to S3 bucket
2. Go to AWS Bedrock Console → Knowledge Bases
3. Select your knowledge base
4. Click "Sync"
5. Wait for completion and check for errors

### Test New Content

- Ask questions about new material in the app
- Verify bot can answer from new lectures
- Check follow-up suggestions are relevant

---

## Monitoring & Maintenance

### Health Checks

- Visit app URL regularly
- Test: questions, voice playback, follow-ups, portfolio examples
- Monitor Streamlit Cloud analytics
- Track AWS Bedrock and ElevenLabs costs

### View Logs

Streamlit Cloud → Your app → Manage app → Logs

### Update Dependencies

```bash
# Update requirements.txt
pip freeze > requirements.txt

# Commit and push
git add requirements.txt
git commit -m "Update dependencies"
git push origin main
```

---

## Rollback Procedure

If deployment breaks:

```bash
# Find last working commit
git log

# Revert to that commit
git revert HEAD
# or
git reset --hard COMMIT_HASH

# Force push to GitHub
git push origin main --force
```

Streamlit Cloud will auto-deploy the reverted version.

---

## Security Best Practices

### DO:
- Store all credentials in Streamlit secrets
- Use environment variables
- Rotate keys regularly
- Use .gitignore for local secrets

### DON'T:
- Commit secrets to GitHub
- Share secrets in chat/email
- Hardcode API keys in code
- Use root AWS credentials

---

## Quick Reference

```bash
# Check status
git status

# Stage, commit, push (triggers deployment)
git add .
git commit -m "Your message"
git push origin main

# View recent commits
git log --oneline -10

# Check remote URL
git remote -v

# Pull latest changes
git pull origin main
```

---

## Current Setup

**Repository**: https://github.com/perfectedpixels/lecture-bot
**Live App**: https://lecture-bot.streamlit.app *(verify this is still current)*
**Main File**: `app/streamlit_app_redesign.py`
**Knowledge Base ID**: `HHYCUJH32J`
**Region**: `us-east-1`

---

## Support Resources

- Streamlit Docs: https://docs.streamlit.io/
- Streamlit Community: https://discuss.streamlit.io/
- AWS Bedrock Docs: https://docs.aws.amazon.com/bedrock/
- GitHub Docs: https://docs.github.com/

---

*This steering document is set to manual inclusion. Reference it when working on deployment tasks.*
