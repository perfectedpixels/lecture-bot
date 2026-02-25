#!/bin/bash
# Deploy using AWS Systems Manager (no SSH needed)

set -e

INSTANCE_ID="i-XXXXXXXXX"  # Update with your instance ID

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                                                              ║"
echo "║   🚀 DEPLOYING VIA AWS SYSTEMS MANAGER                      ║"
echo "║                                                              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Find instance ID if not set
if [ "$INSTANCE_ID" = "i-XXXXXXXXX" ]; then
    echo "Finding instance ID..."
    INSTANCE_ID=$(aws ec2 describe-instances \
      --filters "Name=ip-address,Values=54.90.155.67" "Name=instance-state-name,Values=running" \
      --query "Reservations[0].Instances[0].InstanceId" \
      --output text 2>/dev/null)
    
    if [ "$INSTANCE_ID" = "None" ] || [ -z "$INSTANCE_ID" ]; then
        echo "❌ Could not find instance"
        echo "Please update INSTANCE_ID in this script"
        exit 1
    fi
    echo "✓ Found instance: $INSTANCE_ID"
fi
echo ""

# Step 1: Create temp directory and copy files
echo "📦 Step 1: Preparing files..."
TEMP_DIR=$(mktemp -d)
mkdir -p "$TEMP_DIR/data" "$TEMP_DIR/src" "$TEMP_DIR/app"

cp data/teaching_concepts.json "$TEMP_DIR/data/"
cp data/portfolio_image_metadata.json "$TEMP_DIR/data/"
cp data/affinity_map.json "$TEMP_DIR/data/"
cp src/learning_card_generator.py "$TEMP_DIR/src/"
cp src/persona_bot_safe.py "$TEMP_DIR/src/"
cp app/streamlit_app_redesign.py "$TEMP_DIR/app/"

echo "✓ Files prepared in $TEMP_DIR"
echo ""

# Step 2: Upload to S3 temp location
echo "📤 Step 2: Uploading to S3..."
S3_BUCKET="lecture-transcripts-427791004700"
S3_PREFIX="deployment-temp/$(date +%s)"

aws s3 sync "$TEMP_DIR/" "s3://$S3_BUCKET/$S3_PREFIX/" --quiet
echo "✓ Uploaded to s3://$S3_BUCKET/$S3_PREFIX/"
echo ""

# Step 3: Run deployment via SSM
echo "🔧 Step 3: Running deployment on EC2..."
COMMAND_ID=$(aws ssm send-command \
  --instance-ids "$INSTANCE_ID" \
  --document-name "AWS-RunShellScript" \
  --parameters commands="[
    'cd /home/ec2-user',
    'mkdir -p data src app',
    'aws s3 sync s3://$S3_BUCKET/$S3_PREFIX/data/ data/',
    'aws s3 sync s3://$S3_BUCKET/$S3_PREFIX/src/ src/',
    'aws s3 sync s3://$S3_BUCKET/$S3_PREFIX/app/ app/',
    'sudo systemctl restart lecture-bot || echo Service not found',
    'ls -lh data/*.json src/*.py app/streamlit_app_redesign.py'
  ]" \
  --output text \
  --query "Command.CommandId")

echo "✓ Command sent: $COMMAND_ID"
echo "  Waiting for completion..."
sleep 5

# Step 4: Check results
aws ssm get-command-invocation \
  --command-id "$COMMAND_ID" \
  --instance-id "$INSTANCE_ID" \
  --query "StandardOutputContent" \
  --output text

echo ""
echo "✓ Deployment complete!"
echo ""

# Cleanup
echo "🧹 Cleaning up..."
rm -rf "$TEMP_DIR"
aws s3 rm "s3://$S3_BUCKET/$S3_PREFIX/" --recursive --quiet
echo "✓ Cleanup done"
echo ""

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                                                              ║"
echo "║   ✅ DEPLOYMENT COMPLETE!                                    ║"
echo "║                                                              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "Test at: http://54.90.155.67:8501"
echo ""
