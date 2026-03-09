#!/bin/bash

# Run the Streamlit app
# Usage: ./run.sh

echo "Starting Lecture Bot interface..."
echo "Make sure you have:"
echo "  1. Deployed the infrastructure (see DEPLOYMENT.md)"
echo "  2. Created a Bedrock Knowledge Base"
echo "  3. Uploaded lecture transcripts"
echo ""

# Install dependencies if needed
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -r requirements.txt
else
    source venv/bin/activate
fi

# Run Streamlit (customer UI with UW branding; use streamlit_app.py for admin/dev UI)
streamlit run streamlit_app_redesign.py
