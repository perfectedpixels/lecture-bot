#!/bin/bash

# Test the preprocessing pipeline with sample data
# Usage: ./test_preprocessing.sh

echo "=== Testing Preprocessing Pipeline ==="
echo ""

# Create test directory
TEST_DIR="test_preprocessing"
mkdir -p "$TEST_DIR/raw"
mkdir -p "$TEST_DIR/processed"

# Create sample transcript
cat > "$TEST_DIR/raw/test_lecture.txt" << 'EOF'
Lecture: Introduction to AI and Design
Date: February 10, 2026
Instructor: Jason Levine

00:01:23 Jason Levine: Today we're going to explore the fascinating intersection of artificial intelligence and user experience design.

00:01:45 Jason Levine: When we think about AI in design, we need to consider both the technical capabilities and the human factors.

00:02:10 The key is understanding that AI is a tool, not a replacement for human creativity. In my work, I've found that the best results come from collaboration between designers and AI systems.

00:02:45 Jason Levine: Let me give you an example. When we designed the recommendation system for our e-commerce platform, we used machine learning to understand user preferences.

00:03:15 But we also incorporated design thinking principles to ensure the interface was intuitive and trustworthy.

00:03:45 Jason Levine: This brings us to an important framework I use: the AI-UX Integration Model. It has three key components:

00:04:00 1. Technical feasibility - what can the AI actually do?
00:04:15 2. User needs - what problems are we solving?
00:04:30 3. Ethical considerations - what are the implications?

00:05:00 Jason Levine: Throughout this course, we'll explore each of these areas in depth. Next week, we'll dive into neural networks and how they can be applied to design problems.
EOF

echo "Created sample transcript"
echo ""

# Check if Python dependencies are installed
if ! python3 -c "import boto3" 2>/dev/null; then
    echo "Installing Python dependencies..."
    pip3 install boto3 numpy
fi

# Run preprocessing
echo "Running preprocessing pipeline..."
echo ""

python3 src/preprocessing/pipeline.py \
  "$TEST_DIR/raw/test_lecture.txt" \
  "$TEST_DIR/processed" \
  --speaker "Jason Levine"

# Check results
echo ""
echo "=== Results ==="
echo ""

if [ -f "$TEST_DIR/processed/test_lecture_summary.json" ]; then
    echo "✓ Summary created"
    echo ""
    echo "Summary contents:"
    cat "$TEST_DIR/processed/test_lecture_summary.json" | python3 -m json.tool
    echo ""
fi

SEGMENT_COUNT=$(ls "$TEST_DIR/processed"/test_lecture_segment_*.json 2>/dev/null | wc -l)
echo "✓ Created $SEGMENT_COUNT segment(s)"
echo ""

if [ -f "$TEST_DIR/processed/affinity_map.json" ]; then
    echo "✓ Affinity map created"
    echo ""
    echo "Concept clusters:"
    cat "$TEST_DIR/processed/affinity_map.json" | \
      python3 -c "import sys, json; data=json.load(sys.stdin); [print(f\"  - {c['cluster_id']}: {len(c['concepts'])} concepts\") for c in data.get('clusters', [])]"
    echo ""
fi

echo "=== Test Complete ==="
echo ""
echo "Review processed files in: $TEST_DIR/processed/"
echo ""
echo "To clean up test files:"
echo "  rm -rf $TEST_DIR"
