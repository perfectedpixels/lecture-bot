#!/bin/bash
# Start EC2 instance and wait for it to be ready

INSTANCE_ID="i-0a6f9e8c7b5d4a3e2"  # Update with your instance ID

echo "🚀 Starting EC2 instance..."
echo ""

# Start the instance
aws ec2 start-instances --instance-ids "$INSTANCE_ID"

echo "⏳ Waiting for instance to start..."
aws ec2 wait instance-running --instance-ids "$INSTANCE_ID"

echo "✓ Instance is running!"
echo ""

# Get the public IP
PUBLIC_IP=$(aws ec2 describe-instances \
    --instance-ids "$INSTANCE_ID" \
    --query 'Reservations[0].Instances[0].PublicIpAddress' \
    --output text)

echo "📍 Public IP: $PUBLIC_IP"
echo ""

echo "⏳ Waiting for SSH to be ready (this may take 30-60 seconds)..."
sleep 30

echo ""
echo "✅ EC2 instance is ready!"
echo ""
echo "Next steps:"
echo "  1. Update EC2_HOST in deploy_learning_cards.sh to: ec2-user@$PUBLIC_IP"
echo "  2. Run: ./deploy_learning_cards.sh"
echo ""
echo "Or SSH directly:"
echo "  ssh -i ~/lecture-bot-keypair.pem ec2-user@$PUBLIC_IP"
