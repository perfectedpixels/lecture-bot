# Deploy to Streamlit Cloud (Easiest Option)

## Why Streamlit Cloud?
- ✅ **Free** for public apps
- ✅ **No firewall issues** - runs on Streamlit's infrastructure
- ✅ **Auto-deploys** from GitHub
- ✅ **Public URL** instantly (e.g., `lecture-bot.streamlit.app`)
- ✅ **No server management** - just push code
- ⚠️ Still needs AWS credentials for Bedrock API

## Prerequisites
- GitHub account
- Streamlit Cloud account (free at https://streamlit.io/cloud)
- AWS credentials (for Bedrock API access)

---

## Step 1: Push Code to GitHub (5 minutes)

### Create GitHub Repo
```bash
# Initialize git if not already
git init

# Create .gitignore
cat > .gitignore << 'EOF'
*.pyc
__pycache__/
.DS_Store
*.pem
.env
app/.streamlit/secrets.toml
venv/
*.log
EOF

# Add files
git add .
git commit -m "Initial commit - Learning Cards feature"

# Create repo on GitHub (via web interface)
# Then push:
git remote add origin https://github.com/YOUR_USERNAME/lecture-bot.git
git branch -M main
git push -u origin main
```

---

## Step 2: Create Streamlit Cloud App (3 minutes)

1. Go to: https://share.streamlit.io/
2. Click "New app"
3. Connect your GitHub account
4. Select:
   - **Repository**: `YOUR_USERNAME/lecture-bot`
   - **Branch**: `main`
   - **Main file path**: `app/streamlit_app_redesign.py`
5. Click "Deploy"

---

## Step 3: Add Secrets (2 minutes)

In Streamlit Cloud dashboard:

1. Click on your app
2. Click "Settings" (⚙️)
3. Click "Secrets"
4. Add this TOML:

```toml
# AWS Credentials (from your personal AWS account)
AWS_ACCESS_KEY_ID = "YOUR_ACCESS_KEY"
AWS_SECRET_ACCESS_KEY = "YOUR_SECRET_KEY"
AWS_DEFAULT_REGION = "us-east-1"

# ElevenLabs
ELEVENLABS_API_KEY = "sk_056db134bc26b4a70766c7b9442e5d5b27805389213bdcfb"

# Knowledge Base (you'll need to create this in personal AWS)
KB_ID_515 = "YOUR_KB_ID"
KB_ID_512 = "YOUR_KB_ID"
```

5. Click "Save"

---

## Step 4: Create Requirements File

Create `app/requirements.txt`:

```txt
streamlit>=1.28.0
boto3>=1.28.0
anthropic>=0.3.0
elevenlabs>=0.2.0
```

Commit and push:
```bash
git add app/requirements.txt
git commit -m "Add requirements"
git push
```

Streamlit Cloud will auto-redeploy.

---

## Step 5: Move AWS Resources to Personal Account

You'll need to recreate in your personal AWS account:

### A. Create S3 Bucket
```bash
# Use your personal AWS credentials
aws s3 mb s3://lecture-bot-personal-YOURNAME

# Upload data
aws s3 cp data/ s3://lecture-bot-personal-YOURNAME/data/ --recursive
aws s3 cp data/portfolio_images/ s3://lecture-bot-personal-YOURNAME/portfolio_images/ --recursive
```

### B. Create Bedrock Knowledge Base
1. Go to Bedrock Console in personal account
2. Enable Claude models
3. Create Knowledge Base pointing to your S3 bucket
4. Sync data
5. Copy the Knowledge Base ID

### C. Update Secrets in Streamlit Cloud
Update the `KB_ID_515` with your new Knowledge Base ID.

---

## Pros & Cons

### ✅ Pros
- No firewall issues
- Free hosting
- Auto-deploys from GitHub
- Public URL
- No server management
- SSL/HTTPS included

### ⚠️ Cons
- App goes to sleep after inactivity (wakes on first request)
- Limited to 1GB RAM on free tier
- Still need AWS account for Bedrock
- Public by default (can make private on paid plan)

---

## Alternative: Personal AWS Account

If you want full control, create a personal AWS account and deploy there.

**Cost**: ~$30-50/month for EC2 + Bedrock usage

---

## Recommended Approach

1. **Quick test**: Use Streamlit Cloud (10 minutes)
2. **Production**: Move to personal AWS account if you need:
   - More resources
   - Private deployment
   - Custom domain
   - No sleep mode

---

## Next Steps

Choose your path:
- **Path A**: Streamlit Cloud (follow steps above)
- **Path B**: Personal AWS account (I'll create migration guide)

Which would you prefer?
