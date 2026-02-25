#!/bin/bash
# Complete setup for all learning card features

set -e

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                                                              ║"
echo "║   🔧 SETTING UP ALL LEARNING CARD FEATURES                  ║"
echo "║                                                              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""

# Step 1: Update S3 URLs
echo "📸 Step 1: Updating portfolio image S3 URLs..."
python3 scripts/update_s3_urls.py
echo ""

# Step 2: Generate affinity map (optional - takes a few minutes)
if [ ! -f "data/affinity_map.json" ]; then
    echo "🗺️  Step 2: Generating affinity map..."
    echo "This will take 2-3 minutes..."
    python3 scripts/generate_affinity_map.py
    echo ""
else
    echo "✓ Affinity map already exists (data/affinity_map.json)"
    echo "  To regenerate, delete the file and run this script again"
    echo ""
fi

# Step 3: Run pre-flight check
echo "✈️  Step 3: Running pre-flight check..."
./preflight_check.sh
echo ""

echo "╔══════════════════════════════════════════════════════════════╗"
echo "║                                                              ║"
echo "║   ✅ SETUP COMPLETE!                                         ║"
echo "║                                                              ║"
echo "╚══════════════════════════════════════════════════════════════╝"
echo ""
echo "📝 Next steps:"
echo "   1. Update EC2_HOST in deploy_learning_cards.sh"
echo "   2. Run: ./deploy_learning_cards.sh"
echo ""
