#!/bin/bash
# Move EC2 instance from isolated security group to one that allows access

echo "🔓 Fixing Isolated EC2 Instance"
echo "================================"
echo ""

# Get instance ID
echo "1. Finding instance..."
INSTANCE_ID=$(aws ec2 describe-instances \
  --filters "Name=private-ip-address,Values=172.31.17.82" "Name=instance-state-name,Values=running" \
  --query "Reservations[0].Instances[0].InstanceId" \
  --output text 2>/dev/null)

if [ "$INSTANCE_ID" = "None" ] || [ -z "$INSTANCE_ID" ]; then
    echo "   ❌ Could not find instance"
    exit 1
fi

echo "   Instance ID: $INSTANCE_ID"
echo ""

# Get VPC ID
VPC_ID=$(aws ec2 describe-instances \
  --instance-ids "$INSTANCE_ID" \
  --query "Reservations[0].Instances[0].VpcId" \
  --output text)

echo "   VPC ID: $VPC_ID"
echo ""

# Check if a suitable security group exists
echo "2. Looking for existing security group..."
EXISTING_SG=$(aws ec2 describe-security-groups \
  --filters "Name=vpc-id,Values=$VPC_ID" "Name=group-name,Values=lecture-bot-sg" \
  --query "SecurityGroups[0].GroupId" \
  --output text 2>/dev/null)

if [ "$EXISTING_SG" != "None" ] && [ -n "$EXISTING_SG" ]; then
    echo "   ✓ Found existing: $EXISTING_SG"
    NEW_SG="$EXISTING_SG"
else
    echo "   Creating new security group..."
    
    # Get your current IP
    MY_IP=$(curl -s https://checkip.amazonaws.com)
    
    # Create new security group
    NEW_SG=$(aws ec2 create-security-group \
      --group-name "lecture-bot-sg" \
      --description "Security group for lecture bot with SSH and HTTP access" \
      --vpc-id "$VPC_ID" \
      --output text \
      --query "GroupId")
    
    echo "   ✓ Created: $NEW_SG"
    echo ""
    
    # Add rules
    echo "3. Adding security rules..."
    
    # SSH from your IP
    aws ec2 authorize-security-group-ingress \
      --group-id "$NEW_SG" \
      --protocol tcp \
      --port 22 \
      --cidr "$MY_IP/32" \
      --group-name "SSH from my IP"
    echo "   ✓ SSH (port 22) from $MY_IP"
    
    # HTTP from anywhere
    aws ec2 authorize-security-group-ingress \
      --group-id "$NEW_SG" \
      --protocol tcp \
      --port 80 \
      --cidr "0.0.0.0/0"
    echo "   ✓ HTTP (port 80) from anywhere"
    
    # HTTPS from anywhere
    aws ec2 authorize-security-group-ingress \
      --group-id "$NEW_SG" \
      --protocol tcp \
      --port 443 \
      --cidr "0.0.0.0/0"
    echo "   ✓ HTTPS (port 443) from anywhere"
    
    # Streamlit from anywhere
    aws ec2 authorize-security-group-ingress \
      --group-id "$NEW_SG" \
      --protocol tcp \
      --port 8501 \
      --cidr "0.0.0.0/0"
    echo "   ✓ Streamlit (port 8501) from anywhere"
    
    # Allow all outbound
    aws ec2 authorize-security-group-egress \
      --group-id "$NEW_SG" \
      --protocol all \
      --cidr "0.0.0.0/0" 2>/dev/null || echo "   ✓ Outbound already allowed"
fi

echo ""
echo "4. Updating instance security group..."
aws ec2 modify-instance-attribute \
  --instance-id "$INSTANCE_ID" \
  --groups "$NEW_SG"

echo "   ✓ Instance updated to use $NEW_SG"
echo ""

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                                                              ║"
echo "║   ✅ SECURITY GROUP FIXED!                                   ║"
echo "║                                                              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "Wait 10 seconds, then test:"
echo "  ssh ec2-user@54.90.155.67"
echo ""
echo "If SSH still doesn't work, you may need to:"
echo "  1. Add your SSH key to the instance"
echo "  2. Or use AWS Systems Manager Session Manager"
echo ""
