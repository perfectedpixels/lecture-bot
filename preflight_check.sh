#!/bin/bash
# Pre-flight check before deployment

echo "🔍 PRE-FLIGHT CHECK FOR LEARNING CARDS DEPLOYMENT"
echo "=================================================="
echo ""

ERRORS=0

# Check 1: Data files exist
echo "📦 Checking data files..."
if [ -f "data/teaching_concepts.json" ]; then
    echo "  ✓ teaching_concepts.json found"
else
    echo "  ❌ teaching_concepts.json NOT FOUND"
    ERRORS=$((ERRORS + 1))
fi

if [ -f "data/portfolio_image_metadata.json" ]; then
    echo "  ✓ portfolio_image_metadata.json found"
else
    echo "  ❌ portfolio_image_metadata.json NOT FOUND"
    ERRORS=$((ERRORS + 1))
fi
echo ""

# Check 2: Backend files exist
echo "🔧 Checking backend files..."
if [ -f "src/learning_card_generator.py" ]; then
    echo "  ✓ learning_card_generator.py found"
else
    echo "  ❌ learning_card_generator.py NOT FOUND"
    ERRORS=$((ERRORS + 1))
fi

if [ -f "src/persona_bot_safe.py" ]; then
    echo "  ✓ persona_bot_safe.py found"
else
    echo "  ❌ persona_bot_safe.py NOT FOUND"
    ERRORS=$((ERRORS + 1))
fi
echo ""

# Check 3: UI file exists
echo "🎨 Checking UI files..."
if [ -f "app/streamlit_app_redesign.py" ]; then
    echo "  ✓ streamlit_app_redesign.py found"
else
    echo "  ❌ streamlit_app_redesign.py NOT FOUND"
    ERRORS=$((ERRORS + 1))
fi
echo ""

# Check 4: Python syntax
echo "🐍 Checking Python syntax..."
python3 -m py_compile src/learning_card_generator.py 2>/dev/null
if [ $? -eq 0 ]; then
    echo "  ✓ learning_card_generator.py syntax OK"
else
    echo "  ❌ learning_card_generator.py has syntax errors"
    ERRORS=$((ERRORS + 1))
fi

python3 -m py_compile src/persona_bot_safe.py 2>/dev/null
if [ $? -eq 0 ]; then
    echo "  ✓ persona_bot_safe.py syntax OK"
else
    echo "  ❌ persona_bot_safe.py has syntax errors"
    ERRORS=$((ERRORS + 1))
fi

python3 -m py_compile app/streamlit_app_redesign.py 2>/dev/null
if [ $? -eq 0 ]; then
    echo "  ✓ streamlit_app_redesign.py syntax OK"
else
    echo "  ❌ streamlit_app_redesign.py has syntax errors"
    ERRORS=$((ERRORS + 1))
fi
echo ""

# Check 5: JSON validity
echo "📋 Checking JSON files..."
python3 -c "import json; json.load(open('data/teaching_concepts.json'))" 2>/dev/null
if [ $? -eq 0 ]; then
    echo "  ✓ teaching_concepts.json is valid JSON"
else
    echo "  ❌ teaching_concepts.json is invalid JSON"
    ERRORS=$((ERRORS + 1))
fi

python3 -c "import json; json.load(open('data/portfolio_image_metadata.json'))" 2>/dev/null
if [ $? -eq 0 ]; then
    echo "  ✓ portfolio_image_metadata.json is valid JSON"
else
    echo "  ❌ portfolio_image_metadata.json is invalid JSON"
    ERRORS=$((ERRORS + 1))
fi
echo ""

# Check 6: Deploy script exists
echo "🚀 Checking deployment script..."
if [ -f "deploy_learning_cards.sh" ]; then
    echo "  ✓ deploy_learning_cards.sh found"
    if [ -x "deploy_learning_cards.sh" ]; then
        echo "  ✓ deploy_learning_cards.sh is executable"
    else
        echo "  ⚠️  deploy_learning_cards.sh is not executable (run: chmod +x deploy_learning_cards.sh)"
    fi
else
    echo "  ❌ deploy_learning_cards.sh NOT FOUND"
    ERRORS=$((ERRORS + 1))
fi
echo ""

# Summary
echo "=================================================="
if [ $ERRORS -eq 0 ]; then
    echo "✅ PRE-FLIGHT CHECK PASSED!"
    echo ""
    echo "Ready to deploy. Run:"
    echo "  ./deploy_learning_cards.sh"
    echo ""
    echo "⚠️  REMEMBER TO UPDATE EC2_HOST IN deploy_learning_cards.sh"
    exit 0
else
    echo "❌ PRE-FLIGHT CHECK FAILED ($ERRORS errors)"
    echo ""
    echo "Fix the errors above before deploying."
    exit 1
fi
