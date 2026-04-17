# Deploy Lecture Bot to Streamlit Cloud

## Why Streamlit Cloud?
- Free hosting
- Deploys directly from GitHub
- No EC2 or security group issues
- No corporate AWS account needed
- Students access via a streamlit.app URL

## Prerequisites
1. GitHub account
2. This repo pushed to GitHub (can be private)
3. AWS credentials (from your personal account)

## Step 1: Push to GitHub

```bash
# Create a new GitHub repo (or use existing)
git init
git add .
git commit -m "Lecture bot app"
git remote add origin https://github.com/YOUR_USERNAME/lecture-bot.git
git push -u origin main
```

Make sure `.env` is in `.gitignore` so credentials aren't pushed.

## Step 2: Deploy on Streamlit Cloud

1. Go to https://share.streamlit.io
2. Sign in with GitHub
3. Click "New app"
4. Select your repo, branch (`main`), and main file (`app/streamlit_app.py`)
5. Click "Deploy"

## Step 3: Add Secrets

In Streamlit Cloud, go to your app → Settings → Secrets, and add:

```toml
AWS_ACCESS_KEY_ID = "your_aws_access_key_here"
AWS_SECRET_ACCESS_KEY = "your_aws_secret_key_here"
AWS_REGION = "us-east-1"
KNOWLEDGE_BASE_ID = "HHYCUJH32J"
```

## Step 4: Verify

Your app will be available at:
```
https://YOUR_APP_NAME.streamlit.app
```

Share this URL with students.

## Step 5: Close Corporate Account Resources

After verifying the Streamlit Cloud deployment works:

1. Terminate EC2 instance `i-063c08f998f8cf2da` on corporate account
2. Delete security group `sg-074bba325998cc1db` (after instance is terminated)
3. Remove any other resources on the corporate account
4. Reply to the security ticket confirming the instance has been terminated

## Security Ticket Response Template

```
Hi team,

The exposed Streamlit instance at 54.90.155.67 has been terminated.
- EC2 instance i-063c08f998f8cf2da: TERMINATED
- Security group sg-074bba325998cc1db: DELETED
- No replacement instance on this account

The application has been migrated to Streamlit Cloud (streamlit.app)
which is not hosted on this AWS account.

Please confirm this resolves the issue.
```

## Notes
- Streamlit Cloud free tier allows 1 private app
- If you need auth, Streamlit Cloud supports GitHub-based auth
- All AWS resources (Knowledge Base, S3) remain on personal account 427791004700
- No corporate AWS resources are used
