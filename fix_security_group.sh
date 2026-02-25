#!/bin/bash
# Fix EC2 security group to allow SSH from your current IP

echo "🔒 Fixing EC2 Security Group for SSH Access"
echo "==========================================="
echo ""

# Get your current public IP
echo "1. Getting your current public IP..."
MY_IP=$(curl -s https://checkip.amazonaws.com)
echo "   Your IP: $MY_IP"
echo ""

# Get the security group ID for the EC2 instance
echo "2. Finding security group..."
INSTANCE_ID=$(aws ec2 describe-instances \
  --filters "Name=ip-address,Values=54.90.155.67" \
  --query "Reservations[0].Instances[0].InstanceId" \
  --output text 2>/dev/null)

if [ "$INSTANCE_ID" = "None" ] || [ -z "$INSTANCE_ID" ]; then
    echo "   ⚠️  Could not find instance automatically"
    echo ""
    echo "Manual steps:"
    echo "1. Go to: https://console.aws.amazon.com/ec2/"
    echo "2. Click on your instance"
    echo "3. Click on the Security tab"
    echo "4. Click on the security group link"
    echo "5. Click 'Edit inbound rules'"
    echo "6. Add rule: Type=SSH, Source=My IP ($MY_IP/32)"
    echo "7. Save rules"
    exit 1
fi

echo "   Instance ID: $INSTANCE_ID"

SG_ID=$(aws ec2 describe-instances \
  --instance-ids "$INSTANCE_ID" \
  --query "Reservations[0].Instances[0].SecurityGroups[0].GroupId" \
  --output text)

echo "   Security Group: $SG_ID"
echo ""

# Add SSH rule for your IP
echo "3. Adding SSH rule for your IP..."
aws ec2 authorize-security-group-ingress \
  --group-id "$SG_ID" \
  --protocol tcp \
  --port 22 \
  --cidr "$MY_IP/32" 2>&1 | grep -v "already exists" || echo "   ✓ Rule added (or already exists)"

echo ""
echo "✅ Security group updated!"
echo ""
echo "Wait 10 seconds, then test SSH:"
echo "  ssh ec2-user@54.90.155.67"
echo ""
