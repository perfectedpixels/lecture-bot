# Start EC2 and Deploy Learning Cards

## Step 1: Start EC2 Instance

### Via AWS Console
1. Go to: https://console.aws.amazon.com/ec2/
2. Find your instance: `lecture-bot-server`
3. Select it and click **Actions → Instance State → Start**
4. Wait ~30 seconds for it to start
5. **Copy the new Public IPv4 address** (it changes each time unless you have Elastic IP)

### Via AWS CLI
```bash
# Find your instance ID
aws ec2 describe-instances \
  --filters "Name=tag:Name,Values=lecture-bot-server" \
  --query "Reservations[0].Instances[0].InstanceId" \
  --output text

# Start it (replace with your instance ID)
aws ec2 start-instances --instance-ids i-XXXXXXXXX

# Wait for it to be running
aws ec2 wait instance-running --instance-ids i-XXXXXXXXX

# Get the new IP
aws ec2 describe-instances \
  --instance-ids i-XXXXXXXXX \
  --query "Reservations[0].Instances[0].PublicIpAddress" \
  --output text
```

---

## Step 2: Update Deploy Script

Edit `deploy_learning_cards.sh`:

```bash
# Update this line with your NEW IP address
EC2_HOST="ec2-user@YOUR_NEW_IP_HERE"

# Example:
EC2_HOST="ec2-user@54.165.227.91"
```

Also update `diagnose_ec2.sh` with the same IP if you want to use diagnostics.

---

## Step 3: Test SSH Connection

```bash
# Test you can connect (replace with your IP and key)
ssh -i ~/lecture-bot-keypair.pem ec2-user@YOUR_NEW_IP

# If it works, you'll see the EC2 prompt
# Type 'exit' to disconnect
```

---

## Step 4: Run Setup (First Time Only)

If you haven't run setup yet:

```bash
./setup_all_features.sh
```

This will:
- Update S3 URLs for portfolio images
- Generate affinity map from lectures (~3 minutes)
- Run pre-flight validation

---

## Step 5: Deploy

```bash
./deploy_learning_cards.sh
```

This will:
- Upload data files (teaching concepts, portfolio metadata, affinity map)
- Upload backend code (learning_card_generator.py, persona_bot_safe.py)
- Upload UI code (streamlit_app_redesign.py)
- Restart Streamlit service

---

## Step 6: Test

Visit: `http://YOUR_NEW_IP:8501`

Or if you have a domain: `https://lecture-bot.jllevine.people.aws.dev`

Test:
1. Ask: "What is user research?"
2. Watch skeleton loading appear
3. Verify all three card sections show
4. Test button interactions
5. Check images display

---

## Troubleshooting

### Can't SSH to EC2
- Check security group allows SSH (port 22) from your IP
- Verify key file permissions: `chmod 400 ~/lecture-bot-keypair.pem`
- Make sure you're using the NEW IP address

### Site Not Loading
```bash
# Check if service is running
ssh -i ~/lecture-bot-keypair.pem ec2-user@YOUR_IP
sudo systemctl status lecture-bot

# If not running, start it
sudo systemctl start lecture-bot

# Check logs
sudo journalctl -u lecture-bot -f
```

### Service Won't Start
```bash
# Test imports manually
ssh -i ~/lecture-bot-keypair.pem ec2-user@YOUR_IP
cd /home/ec2-user
source app/venv/bin/activate
python3 -c "import sys; sys.path.insert(0, 'src'); from persona_bot_safe import PersonaBot; print('OK')"
```

### Wrong App Running
The service might be configured to run the old app. Check:
```bash
sudo cat /etc/systemd/system/lecture-bot.service | grep ExecStart

# Should show: streamlit run streamlit_app_redesign.py
# If it shows streamlit_app_simple.py, update the service file
```

---

## Quick Commands Reference

```bash
# Start EC2 (if you have instance ID)
aws ec2 start-instances --instance-ids i-XXXXXXXXX

# Get new IP
aws ec2 describe-instances --instance-ids i-XXXXXXXXX \
  --query "Reservations[0].Instances[0].PublicIpAddress" --output text

# Test SSH
ssh -i ~/lecture-bot-keypair.pem ec2-user@NEW_IP

# Deploy
./deploy_learning_cards.sh

# Check service
ssh -i ~/lecture-bot-keypair.pem ec2-user@NEW_IP 'sudo systemctl status lecture-bot'

# View logs
ssh -i ~/lecture-bot-keypair.pem ec2-user@NEW_IP 'sudo journalctl -u lecture-bot -f'
```

---

## Note About IP Changes

Every time you stop/start EC2, the IP changes (unless you have an Elastic IP).

**To avoid this**:
1. Go to EC2 Console → Elastic IPs
2. Allocate new Elastic IP
3. Associate it with your instance
4. Use that IP in all scripts (it won't change)

**Cost**: Elastic IPs are free while instance is running, ~$0.005/hour when stopped.

---

## Ready?

1. ✅ Start EC2
2. ✅ Get new IP
3. ✅ Update deploy_learning_cards.sh
4. ✅ Run ./setup_all_features.sh (if first time)
5. ✅ Run ./deploy_learning_cards.sh
6. ✅ Test at http://NEW_IP:8501

Let's go! 🚀
