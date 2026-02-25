#!/bin/bash
# Diagnose EC2 deployment issues

EC2_HOST="ec2-user@54.90.155.67"
KEY_FILE="~/lecture-bot-keypair.pem"  # Update with your key path

echo "🔍 DIAGNOSING EC2 DEPLOYMENT"
echo "=============================="
echo ""

echo "1. Checking service status..."
ssh -i "$KEY_FILE" "$EC2_HOST" << 'ENDSSH'
    sudo systemctl status lecture-bot --no-pager | head -20
ENDSSH
echo ""

echo "2. Checking recent logs..."
ssh -i "$KEY_FILE" "$EC2_HOST" << 'ENDSSH'
    echo "Last 30 lines of logs:"
    sudo journalctl -u lecture-bot -n 30 --no-pager
ENDSSH
echo ""

echo "3. Checking file existence..."
ssh -i "$KEY_FILE" "$EC2_HOST" << 'ENDSSH'
    echo "Data files:"
    ls -lh data/*.json 2>&1 | tail -5
    echo ""
    echo "Source files:"
    ls -lh src/learning_card_generator.py src/persona_bot_safe.py 2>&1
    echo ""
    echo "App file:"
    ls -lh app/streamlit_app_redesign.py 2>&1
ENDSSH
echo ""

echo "4. Testing Python imports..."
ssh -i "$KEY_FILE" "$EC2_HOST" << 'ENDSSH'
    cd /home/ec2-user
    source app/venv/bin/activate 2>/dev/null || echo "⚠️  venv not found"
    
    echo "Testing imports:"
    python3 -c "import sys; sys.path.insert(0, 'src'); from persona_bot_safe import PersonaBot; print('✓ PersonaBot OK')" 2>&1
    python3 -c "import sys; sys.path.insert(0, 'src'); from learning_card_generator import LearningCardGenerator; print('✓ LearningCardGenerator OK')" 2>&1
ENDSSH
echo ""

echo "5. Checking which app is running..."
ssh -i "$KEY_FILE" "$EC2_HOST" << 'ENDSSH'
    echo "Service configuration:"
    sudo cat /etc/systemd/system/lecture-bot.service 2>&1 | grep ExecStart
ENDSSH
echo ""

echo "=============================="
echo "Diagnosis complete!"
echo ""
echo "Common issues:"
echo "  • Service not running → sudo systemctl start lecture-bot"
echo "  • Import errors → Check logs above"
echo "  • Wrong app file → Service might be running streamlit_app_simple.py"
echo "  • Missing files → Re-run deployment"
