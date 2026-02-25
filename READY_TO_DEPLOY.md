# 🚀 Ready to Deploy Learning Cards!

## Pre-Flight Status: ✅ PASSED

All files are ready for deployment. Here's what you need to do:

## Quick Start (3 steps)

### 1. Update EC2 Connection Info

Edit `deploy_learning_cards.sh` and update these lines:

```bash
EC2_HOST="ec2-user@YOUR_EC2_IP_HERE"
KEY_FILE="~/YOUR_KEY_FILE.pem"
```

### 2. Run Deployment

```bash
./deploy_learning_cards.sh
```

### 3. Test

Visit your EC2 URL and ask: "What is user research?"

You should see learning cards appear below the response!

---

## What Gets Deployed

### Data Files (2)
- ✅ `data/teaching_concepts.json` (20 concepts)
- ✅ `data/portfolio_image_metadata.json` (208 images, 21 projects)

### Backend Files (2)
- ✅ `src/learning_card_generator.py` (card generation engine)
- ✅ `src/persona_bot_safe.py` (updated with card integration)

### UI Files (1)
- ✅ `app/streamlit_app_redesign.py` (card rendering components)

---

## Expected Behavior After Deployment

### ✅ What Should Work
1. Bot responds to questions normally
2. Learning cards appear after most recent response
3. Three card sections visible:
   - 📚 Core Teaching Concepts (with definitions)
   - 🔗 Related Concepts (may be empty without affinity map)
   - 🎨 See It in Practice (portfolio examples)
4. "Learn more" buttons expand inline content
5. "Ask Professor Levine" buttons submit new queries
6. Portfolio project info displays (images won't show until S3 upload)

### ⚠️ Expected Limitations
1. Related Concepts card will be empty (needs affinity_map.json)
2. Portfolio images won't display (need S3 URLs)
3. Card generation adds ~2-3 seconds to response time
4. First query after restart may be slower (cold start)

### ❌ What Might Break
1. **Import errors** - Fixed with try/except in persona_bot_safe.py
2. **File not found** - Deploy script uploads to correct locations
3. **AWS credentials** - Should work if existing app works
4. **Service restart** - Script handles this automatically

---

## Troubleshooting Quick Reference

### If cards don't appear:
```bash
# Check logs on EC2
ssh -i ~/lecture-bot-keypair.pem ec2-user@YOUR_IP
sudo journalctl -u lecture-bot -f

# Look for:
# "✓ Learning card generator initialized" = Good!
# "⚠️  Learning card generator disabled" = Check error message
```

### If service won't start:
```bash
# On EC2, test imports manually
cd /home/ec2-user
source app/venv/bin/activate
python3 -c "from src.learning_card_generator import LearningCardGenerator; print('OK')"
```

### If you need to rollback:
```bash
# Just restart with old app
ssh -i ~/lecture-bot-keypair.pem ec2-user@YOUR_IP
sudo systemctl stop lecture-bot
cd app
source venv/bin/activate
streamlit run streamlit_app_simple.py --server.port 8501
```

---

## Deployment Checklist

Before running deploy script:
- [ ] Updated EC2_HOST in deploy_learning_cards.sh
- [ ] Updated KEY_FILE path in deploy_learning_cards.sh
- [ ] Can SSH to EC2: `ssh -i ~/lecture-bot-keypair.pem ec2-user@YOUR_IP`
- [ ] Existing app is working (test current URL)

After deployment:
- [ ] Service restarted successfully
- [ ] App loads without errors
- [ ] Can ask questions and get responses
- [ ] Learning cards appear
- [ ] Buttons are clickable
- [ ] No errors in logs

---

## Files Created for Deployment

### Deployment Tools
- ✅ `deploy_learning_cards.sh` - Main deployment script
- ✅ `preflight_check.sh` - Pre-deployment validation
- ✅ `DEPLOYMENT_CHECKLIST.md` - Detailed troubleshooting guide
- ✅ `READY_TO_DEPLOY.md` - This file

### Implementation Files
- ✅ `src/learning_card_generator.py` - Backend engine
- ✅ `src/persona_bot_safe.py` - Updated bot with cards
- ✅ `app/streamlit_app_redesign.py` - UI with card rendering
- ✅ `data/teaching_concepts.json` - Concept taxonomy
- ✅ `data/portfolio_image_metadata.json` - Tagged images
- ✅ `LEARNING_CARDS_IMPLEMENTATION.md` - Full documentation

---

## What Happens When You Deploy

1. **Uploads data files** to EC2 `/home/ec2-user/data/`
2. **Uploads backend code** to EC2 `/home/ec2-user/src/`
3. **Uploads UI code** to EC2 `/home/ec2-user/app/`
4. **Restarts Streamlit service** (or tells you how to start manually)
5. **Verifies files** are in place
6. **Shows status** and next steps

Total time: ~2-3 minutes

---

## Success Criteria

Deployment is successful if:
- ✅ No errors during upload
- ✅ Service restarts without errors
- ✅ App loads in browser
- ✅ Can ask questions
- ✅ Learning cards appear (even if some are empty)
- ✅ Buttons work

---

## Next Steps After Successful Deployment

### Immediate (5 minutes)
1. Test with various questions
2. Check all three card types
3. Test button interactions
4. Monitor logs for errors

### Short-term (1 hour)
1. Test on mobile device
2. Check performance (response time)
3. Verify no memory leaks
4. Test with multiple users

### Medium-term (1 week)
1. Upload portfolio images to S3
2. Generate affinity_map.json
3. Optimize card generation speed
4. Gather user feedback

---

## Support

If you encounter issues:

1. **Check logs first**: `sudo journalctl -u lecture-bot -f`
2. **Review DEPLOYMENT_CHECKLIST.md** for detailed troubleshooting
3. **Test imports manually** on EC2
4. **Verify file paths** and permissions
5. **Check AWS credentials** in secrets.toml

---

## Ready? Let's Deploy!

```bash
# 1. Update EC2 connection info in deploy_learning_cards.sh
# 2. Run deployment
./deploy_learning_cards.sh

# 3. Watch it work! 🚀
```

Good luck! The pre-flight check passed, so you're ready to go. 🎉
