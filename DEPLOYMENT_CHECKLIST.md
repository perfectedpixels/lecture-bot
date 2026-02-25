# Learning Cards Deployment Checklist

## Pre-Deployment Checks

### Local Testing
- [ ] Test card generation locally: `python3 test_learning_cards.py`
- [ ] Verify data files exist:
  - [ ] `data/teaching_concepts.json`
  - [ ] `data/portfolio_image_metadata.json`
- [ ] Check import paths in `persona_bot_safe.py`
- [ ] Verify Streamlit app runs locally

### EC2 Connection
- [ ] SSH key file exists and has correct permissions (chmod 400)
- [ ] Can connect to EC2: `ssh -i ~/lecture-bot-keypair.pem ec2-user@<IP>`
- [ ] EC2 IP address is correct in deploy script

## Deployment Steps

### 1. Update Deploy Script
```bash
# Edit deploy_learning_cards.sh
# Update these variables:
EC2_HOST="ec2-user@YOUR_EC2_IP"
KEY_FILE="~/YOUR_KEY_FILE.pem"
```

### 2. Make Script Executable
```bash
chmod +x deploy_learning_cards.sh
```

### 3. Run Deployment
```bash
./deploy_learning_cards.sh
```

## Post-Deployment Verification

### Check Files on EC2
```bash
ssh -i ~/lecture-bot-keypair.pem ec2-user@<IP>

# Verify data files
ls -lh data/teaching_concepts.json
ls -lh data/portfolio_image_metadata.json

# Verify backend
ls -lh src/learning_card_generator.py
ls -lh src/persona_bot_safe.py

# Verify UI
ls -lh app/streamlit_app_redesign.py
```

### Check Service Status
```bash
# On EC2
sudo systemctl status lecture-bot

# View logs
sudo journalctl -u lecture-bot -f
```

### Test Application
- [ ] Visit your EC2 URL (http://YOUR_IP:8501 or https://your-domain.com)
- [ ] Ask a test question: "What is user research?"
- [ ] Verify learning cards appear
- [ ] Test "Learn more" button expansion
- [ ] Test "Ask Professor Levine" button
- [ ] Check browser console for errors (F12)

## Common Issues & Solutions

### Issue 1: Import Error - `No module named 'learning_card_generator'`

**Cause**: Import path issue in `persona_bot_safe.py`

**Solution**:
```python
# In persona_bot_safe.py, change:
from .learning_card_generator import LearningCardGenerator

# To:
try:
    from learning_card_generator import LearningCardGenerator
except ImportError:
    from .learning_card_generator import LearningCardGenerator
```

### Issue 2: FileNotFoundError - `data/teaching_concepts.json`

**Cause**: Data files not in correct location

**Solution**:
```bash
# On EC2, check current directory structure
pwd  # Should be /home/ec2-user
ls -la data/

# If data/ doesn't exist, create it
mkdir -p data

# Re-upload files
# From local machine:
scp -i ~/lecture-bot-keypair.pem data/*.json ec2-user@<IP>:/home/ec2-user/data/
```

### Issue 3: Cards Not Appearing

**Cause**: PersonaBot not initialized with card generator

**Check**:
```bash
# On EC2, check logs
sudo journalctl -u lecture-bot -n 50

# Look for:
# "✓ Learning card generator initialized"
# or
# "⚠️  Learning card generator disabled: <error>"
```

**Solution**: Check that `enable_learning_cards=True` in PersonaBot initialization

### Issue 4: Streamlit Service Won't Start

**Cause**: Python import errors or missing dependencies

**Solution**:
```bash
# On EC2
cd /home/ec2-user/app
source venv/bin/activate

# Test imports manually
python3 -c "from learning_card_generator import LearningCardGenerator; print('OK')"
python3 -c "from persona_bot_safe import PersonaBot; print('OK')"

# If errors, check sys.path
python3 -c "import sys; print('\n'.join(sys.path))"

# May need to add parent directory to path in streamlit app
```

### Issue 5: CSS Not Loading

**Cause**: Streamlit caching old version

**Solution**:
```bash
# On EC2
# Clear Streamlit cache
rm -rf /home/ec2-user/.streamlit/cache

# Restart service
sudo systemctl restart lecture-bot

# Or force browser refresh (Ctrl+Shift+R)
```

### Issue 6: Boto3 Credentials Error

**Cause**: AWS credentials not configured on EC2

**Solution**:
```bash
# On EC2, check if secrets.toml exists
cat /home/ec2-user/app/.streamlit/secrets.toml

# Should contain:
# AWS_ACCESS_KEY_ID = "..."
# AWS_SECRET_ACCESS_KEY = "..."
# AWS_DEFAULT_REGION = "us-east-1"

# If missing, create it (use your actual credentials)
```

### Issue 7: Portfolio Images Not Displaying

**Cause**: S3 URLs not set or images not uploaded

**Expected**: Images won't display until you upload them to S3 and update metadata

**Solution**: This is Phase 5 work - for now, cards will show project info without images

## Rollback Plan

If deployment breaks the app:

### Quick Rollback
```bash
# On EC2
cd /home/ec2-user

# Restore old persona_bot_safe.py (if you backed it up)
cp src/persona_bot_safe.py.backup src/persona_bot_safe.py

# Or use the old app
sudo systemctl stop lecture-bot
cd app
source venv/bin/activate
streamlit run streamlit_app_simple.py --server.port 8501
```

### Full Rollback
```bash
# Revert to previous working version
git checkout HEAD~1 src/persona_bot_safe.py
git checkout HEAD~1 app/streamlit_app_redesign.py

# Re-deploy
./deploy_learning_cards.sh
```

## Success Criteria

✅ Deployment successful if:
- [ ] Streamlit service is running
- [ ] App loads without errors
- [ ] Can ask questions and get responses
- [ ] Learning cards appear after bot response
- [ ] At least one card type shows content (Teaching Concepts or Portfolio Examples)
- [ ] Buttons are clickable and functional
- [ ] No Python errors in logs

⚠️ Acceptable issues (can fix later):
- [ ] Related Concepts card empty (needs affinity_map.json)
- [ ] Portfolio images not showing (needs S3 upload)
- [ ] Some styling issues on mobile
- [ ] Slow card generation (can optimize later)

## Monitoring

### Watch Logs in Real-Time
```bash
ssh -i ~/lecture-bot-keypair.pem ec2-user@<IP>
sudo journalctl -u lecture-bot -f
```

### Check Resource Usage
```bash
# On EC2
top  # Check CPU/memory
df -h  # Check disk space
```

### Test Performance
- Time how long it takes to generate cards
- Check if response time is acceptable (<5 seconds)
- Monitor for memory leaks (restart service if needed)

## Next Steps After Successful Deployment

1. **Test with real queries** - Try various question types
2. **Gather feedback** - Share with a test user
3. **Monitor logs** - Watch for errors over 24 hours
4. **Optimize** - If slow, add caching or reduce API calls
5. **Phase 5** - Upload portfolio images to S3
6. **Phase 6** - Create documentation and demo video

## Emergency Contacts

If you get stuck:
- Check logs first: `sudo journalctl -u lecture-bot -f`
- Test imports manually in Python
- Verify file paths and permissions
- Check AWS credentials in secrets.toml
- Restart service: `sudo systemctl restart lecture-bot`

## Deployment Log

Record your deployment:
- **Date**: _______________
- **Time**: _______________
- **EC2 IP**: _______________
- **Issues encountered**: _______________
- **Resolution**: _______________
- **Status**: ✅ Success / ⚠️ Partial / ❌ Failed
