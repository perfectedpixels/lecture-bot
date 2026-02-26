# Lecture Bot Deployment Guide

Complete guide for deploying the Lecture Bot to Streamlit Cloud via GitHub.

---

## Prerequisites

- GitHub account
- Streamlit Cloud account (free tier works)
- AWS account with Bedrock access
- ElevenLabs API key (optional, for voice features)

---

## Part 1: GitHub Setup

### 1.1 Initialize Git Repository (if not already done)

```bash
cd /path/to/lecture-bot
git init
git add .
git commit -m "Initial commit"
```

### 1.2 Create GitHub Repository

1. Go to https://github.com/new
2. Repository name: `lecture-bot` (or your preferred name)
3. Set to **Public** (required for free Streamlit Cloud)
4. Do NOT initialize with README (you already have one)
5. Click "Create repository"

### 1.3 Connect Local to GitHub

```bash
git remote add origin https://github.com/YOUR_USERNAME/lecture-bot.git
git branch -M main
git push -u origin main
```

### 1.4 Verify Files Are Pushed

Check that these critical files are in your GitHub repo:
- `app/streamlit_app_redesign.py` (main app)
- `requirements.txt` (dependencies)
- `src/persona_bot_safe.py` (bot logic)
- `src/learning_card_generator.py` (learning cards)
- `data/uw-background.png` (background image)
- `data/uw-logo.png` (logo image)
- `data/teaching_concepts.json` (teaching concepts)
- `data/portfolio_image_metadata.json` (portfolio metadata)

---

## Part 2: Streamlit Cloud Deployment

### 2.1 Sign Up for Streamlit Cloud

1. Go to https://share.streamlit.io/
2. Click "Sign up" or "Continue with GitHub"
3. Authorize Streamlit to access your GitHub account

### 2.2 Deploy New App

1. Click "New app" button
2. Fill in deployment settings:
   - **Repository**: `YOUR_USERNAME/lecture-bot`
   - **Branch**: `main`
   - **Main file path**: `app/streamlit_app_redesign.py`
3. Click "Deploy!"

### 2.3 Wait for Initial Deployment

- First deployment takes 2-5 minutes
- Watch the logs for any errors
- App will auto-restart when complete

---

## Part 3: Configure Secrets

### 3.1 Add AWS Credentials

1. In Streamlit Cloud, click "Manage app" (bottom right)
2. Click "Settings" → "Secrets"
3. Add the following (use UPPERCASE for AWS keys):

```toml
AWS_ACCESS_KEY_ID = "YOUR_AWS_ACCESS_KEY"
AWS_SECRET_ACCESS_KEY = "YOUR_AWS_SECRET_KEY"
AWS_DEFAULT_REGION = "us-east-1"

KB_ID_515 = "YOUR_KNOWLEDGE_BASE_ID"
KB_ID_512 = "YOUR_OTHER_KB_ID"  # Optional

ELEVENLABS_API_KEY = "YOUR_ELEVENLABS_KEY"  # Optional
```

**CRITICAL**: AWS keys MUST be uppercase:
- ✅ `AWS_ACCESS_KEY_ID`
- ❌ `aws_access_key_id`

### 3.2 Save and Restart

1. Click "Save"
2. App will automatically restart with new secrets
3. Check logs to verify connection

---

## Part 4: Making Updates

### 4.1 Local Development Workflow

```bash
# Make your changes locally
# Test locally if possible

# Stage changes
git add .

# Commit with descriptive message
git commit -m "Description of changes"

# Push to GitHub
git push origin main
```

### 4.2 Automatic Deployment

- Streamlit Cloud watches your GitHub repo
- Any push to `main` branch triggers auto-deployment
- Takes 1-2 minutes to redeploy
- Check logs if deployment fails

### 4.3 Manual Restart

If needed, manually restart the app:
1. Click "Manage app"
2. Click "Reboot app"
3. Wait for restart to complete

---

## Part 5: Common Issues & Solutions

### Issue: "Unable to locate credentials"

**Solution**: Check secrets configuration
- Verify AWS keys are UPPERCASE
- No quotes around values in secrets
- No extra spaces
- Restart app after adding secrets

### Issue: Images not loading

**Solution**: Verify image paths
- Check `data/uw-background.png` exists in GitHub
- Check `data/uw-logo.png` exists in GitHub
- Look at app logs for path errors
- Images must be committed and pushed

### Issue: Import errors

**Solution**: Check requirements.txt
- All dependencies listed
- Correct versions specified
- No typos in package names
- Check logs for specific missing packages

### Issue: App crashes on startup

**Solution**: Check logs
1. Click "Manage app"
2. Click "Logs"
3. Look for error messages
4. Common causes:
   - Missing secrets
   - Import errors
   - File path issues
   - Invalid Python syntax

---

## Part 6: Monitoring & Maintenance

### 6.1 Check App Health

- Visit your app URL regularly
- Test key features:
  - Ask a question
  - Check voice playback
  - Test follow-up buttons
  - Verify portfolio examples

### 6.2 View Logs

Access logs anytime:
1. Go to Streamlit Cloud dashboard
2. Click your app
3. Click "Manage app"
4. Click "Logs"
5. Use search to find specific errors

### 6.3 Update Dependencies

When updating packages:

```bash
# Update requirements.txt locally
pip freeze > requirements.txt

# Or manually edit requirements.txt
# Then commit and push
git add requirements.txt
git commit -m "Update dependencies"
git push origin main
```

---

## Part 7: Adding New Lecture Content

### 7.1 Convert RTF Files (if needed)

```bash
# Install converter
pip3 install striprtf

# Convert RTF to TXT
python3 scripts/convert_rtf_to_txt.py data/rtfs data/converted_lectures
```

### 7.2 Upload to S3

1. Go to AWS S3 Console
2. Navigate to your lecture bucket
3. Upload converted .txt files
4. Verify files are uploaded

### 7.3 Sync Bedrock Knowledge Base

1. Go to AWS Bedrock Console
2. Navigate to Knowledge Bases
3. Select your knowledge base
4. Click "Sync"
5. Wait for sync to complete
6. Check for failed files
7. Fix any errors and re-sync

### 7.4 Test New Content

1. Go to your Streamlit app
2. Ask questions about new lecture content
3. Verify bot can answer from new material
4. Check follow-up suggestions are relevant

---

## Part 8: Backup & Recovery

### 8.1 Backup Strategy

**GitHub is your backup**:
- All code is version controlled
- Can roll back to any previous commit
- Clone repo to new location anytime

**AWS Bedrock**:
- Knowledge Base data stored in S3
- S3 has built-in versioning (enable it!)
- Export important data regularly

### 8.2 Rollback Procedure

If deployment breaks:

```bash
# Find last working commit
git log

# Revert to that commit
git revert HEAD
# or
git reset --hard COMMIT_HASH

# Push to GitHub
git push origin main --force
```

Streamlit Cloud will auto-deploy the reverted version.

---

## Part 9: Performance Optimization

### 9.1 Monitor Usage

- Check Streamlit Cloud analytics
- Monitor AWS Bedrock costs
- Track ElevenLabs API usage

### 9.2 Optimize Costs

**AWS Bedrock**:
- Use appropriate model (Sonnet vs Haiku)
- Limit max_tokens in responses
- Cache frequent queries if possible

**ElevenLabs**:
- Make voice optional (already done)
- Consider caching audio responses
- Monitor monthly usage

### 9.3 Improve Performance

**App Speed**:
- Session state for caching
- Lazy load heavy imports
- Optimize image sizes
- Minimize API calls

---

## Part 10: Security Best Practices

### 10.1 Secrets Management

✅ **DO**:
- Store all credentials in Streamlit secrets
- Use environment variables
- Rotate keys regularly
- Use least-privilege IAM roles

❌ **DON'T**:
- Commit secrets to GitHub
- Share secrets in chat/email
- Use root AWS credentials
- Hardcode API keys

### 10.2 Access Control

- Keep GitHub repo public (required for free tier)
- Don't commit sensitive data
- Use .gitignore for local secrets
- Review commits before pushing

---

## Quick Reference Commands

```bash
# Check git status
git status

# Stage all changes
git add .

# Commit changes
git commit -m "Your message"

# Push to GitHub (triggers deployment)
git push origin main

# View recent commits
git log --oneline -10

# Revert last commit
git revert HEAD

# Check remote URL
git remote -v

# Pull latest changes
git pull origin main
```

---

## Support Resources

- **Streamlit Docs**: https://docs.streamlit.io/
- **Streamlit Community**: https://discuss.streamlit.io/
- **AWS Bedrock Docs**: https://docs.aws.amazon.com/bedrock/
- **GitHub Docs**: https://docs.github.com/

---

## Troubleshooting Checklist

Before asking for help, verify:

- [ ] All files committed and pushed to GitHub
- [ ] Secrets configured correctly (UPPERCASE AWS keys)
- [ ] requirements.txt includes all dependencies
- [ ] App file path is correct in Streamlit settings
- [ ] AWS credentials have proper permissions
- [ ] Knowledge Base is synced and accessible
- [ ] Checked Streamlit Cloud logs for errors
- [ ] Tested locally if possible

---

## Your Current Setup

**Repository**: https://github.com/perfectedpixels/lecture-bot
**Live App**: https://lecture-bot.streamlit.app
**Main File**: `app/streamlit_app_redesign.py`
**Knowledge Base ID**: `1TTBVE6MG2`
**Region**: `us-east-1`

---

*Last Updated: February 26, 2026*
