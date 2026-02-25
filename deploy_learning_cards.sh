#!/bin/bash
# Deploy Learning Cards Feature to EC2

set -e  # Exit on error

# Configuration
EC2_HOST="ec2-user@54.90.155.67"
KEY_FILE="~/lecture-bot-keypair.pem"  # Update with your key path
REMOTE_DIR="/home/ec2-user"

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                                                              ║"
echo "║   🚀 DEPLOYING LEARNING CARDS FEATURE TO EC2                ║"
echo "║                                                              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Step 1: Upload data files
echo "📦 Step 1: Uploading data files..."
scp -i "$KEY_FILE" \
    data/teaching_concepts.json \
    data/portfolio_image_metadata.json \
    data/affinity_map.json \
    "$EC2_HOST:$REMOTE_DIR/data/" 2>/dev/null || \
scp -i "$KEY_FILE" \
    data/teaching_concepts.json \
    data/portfolio_image_metadata.json \
    "$EC2_HOST:$REMOTE_DIR/data/"

echo "✓ Data files uploaded"
echo ""

# Step 2: Upload backend code
echo "🔧 Step 2: Uploading backend code..."
scp -i "$KEY_FILE" \
    src/learning_card_generator.py \
    src/persona_bot_safe.py \
    "$EC2_HOST:$REMOTE_DIR/src/"

echo "✓ Backend code uploaded"
echo ""

# Step 3: Upload UI code
echo "🎨 Step 3: Uploading UI code..."
scp -i "$KEY_FILE" \
    app/streamlit_app_redesign.py \
    "$EC2_HOST:$REMOTE_DIR/app/"

echo "✓ UI code uploaded"
echo ""

# Step 4: Restart Streamlit service
echo "🔄 Step 4: Restarting Streamlit service..."
ssh -i "$KEY_FILE" "$EC2_HOST" << 'ENDSSH'
    # Check if service exists
    if systemctl list-units --full -all | grep -q lecture-bot.service; then
        echo "Restarting lecture-bot service..."
        sudo systemctl restart lecture-bot
        sleep 3
        sudo systemctl status lecture-bot --no-pager
    else
        echo "⚠️  Service not found. You may need to start Streamlit manually."
        echo "Run: cd ~/app && source venv/bin/activate && streamlit run streamlit_app_redesign.py"
    fi
ENDSSH

echo ""
echo "✓ Service restarted"
echo ""

# Step 5: Verify deployment
echo "🔍 Step 5: Verifying deployment..."
ssh -i "$KEY_FILE" "$EC2_HOST" << 'ENDSSH'
    echo "Checking files..."
    ls -lh data/teaching_concepts.json data/portfolio_image_metadata.json 2>/dev/null || echo "⚠️  Data files not found"
    ls -lh src/learning_card_generator.py src/persona_bot_safe.py 2>/dev/null || echo "⚠️  Backend files not found"
    ls -lh app/streamlit_app_redesign.py 2>/dev/null || echo "⚠️  UI file not found"
ENDSSH

echo ""
echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                                                              ║"
echo "║   ✅ DEPLOYMENT COMPLETE!                                    ║"
echo "║                                                              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "📝 Next steps:"
echo "   1. Test the app at your EC2 URL"
echo "   2. Verify learning cards appear after bot responses"
echo "   3. Test inline expansion and buttons"
echo "   4. Check for any errors in logs:"
echo "      ssh -i $KEY_FILE $EC2_HOST 'sudo journalctl -u lecture-bot -f'"
echo ""
