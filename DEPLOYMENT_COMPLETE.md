# Lecture Bot - Deployment Complete! 🎉

## Live URL
**https://lecture-bot.jllevine.people.aws.dev**

## What's Working
✅ Public HTTPS domain with SSL certificate
✅ Multi-course support (COMMLD 515 & 512)
✅ AWS Bedrock Knowledge Base integration
✅ Persona responses as Jason Levine
✅ Safety rules (privacy, authenticity)
✅ Messenger-style chat interface
✅ Follow-up suggestion buttons
✅ Nginx reverse proxy
✅ Systemd service (auto-restart)
✅ Let's Encrypt SSL (auto-renew)

## In Progress
⏳ Voice with waveform visualization (implementing now)

## Infrastructure
- **EC2**: i-063c08f998f8cf2da (t3.medium)
- **IP**: 98.94.65.18
- **Domain**: lecture-bot.jllevine.people.aws.dev
- **Region**: us-east-1
- **Account**: 427791004700

## Services Running
- Nginx (port 80/443)
- Streamlit (port 8501, localhost only)
- Systemd service: lecture-bot.service

## Credentials
- **AWS IAM User**: lecture-bot-user
- **ElevenLabs API Key**: Configured in secrets.toml
- **Knowledge Base ID**: 1TTBVE6MG2

## Maintenance Commands

**SSH to EC2**:
```bash
ssh -i lecture-bot-keypair.pem ec2-user@98.94.65.18
```

**Restart Streamlit**:
```bash
sudo systemctl restart lecture-bot
```

**View logs**:
```bash
sudo journalctl -u lecture-bot -f
```

**Update app**:
```bash
# From local
rsync -avz --exclude='venv' -e "ssh -i lecture-bot-keypair.pem" app/ ec2-user@98.94.65.18:/home/ec2-user/app/
ssh -i lecture-bot-keypair.pem ec2-user@98.94.65.18 "sudo systemctl restart lecture-bot"
```

## Cost Estimate
- EC2 t3.medium: ~$30/month
- S3 storage: ~$1/month
- Bedrock queries: Pay per use
- ElevenLabs: Free tier (10k chars/month)
- Total: ~$32/month

## Next Steps
1. Add waveform visualization for voice
2. Test with students
3. Monitor usage and costs
4. Add more courses as needed

---

**Deployment completed**: February 25, 2026
**Total time**: ~4 hours
