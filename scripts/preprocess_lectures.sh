#!/bin/bash

# Preprocess lecture transcripts
# Usage: ./preprocess_lectures.sh <input_dir> <output_dir>

if [ $# -lt 2 ]; then
    echo "Usage: $0 <input_dir> <output_dir>"
    echo "Example: $0 ./raw_transcripts ./processed_lectures"
    exit 1
fi

INPUT_DIR=$1
OUTPUT_DIR=$2

echo "=== Lecture Preprocessing Pipeline ==="
echo "Input: $INPUT_DIR"
echo "Output: $OUTPUT_DIR"
echo ""

# Check if input directory exists
if [ ! -d "$INPUT_DIR" ]; then
    echo "Error: Input directory does not exist"
    exit 1
fi

# Create output directory
mkdir -p "$OUTPUT_DIR"

# Install dependencies if needed
if [ ! -d "venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
    pip install -r src/preprocessing/requirements.txt
else
    source venv/bin/activate
fi

# Run preprocessing pipeline
echo "Starting preprocessing..."
python3 src/preprocessing/pipeline.py "$INPUT_DIR" "$OUTPUT_DIR"

echo ""
echo "✓ Preprocessing complete!"
echo ""
echo "Next steps:"
echo "1. Review processed files in $OUTPUT_DIR"
echo "2. Upload to S3: aws s3 sync $OUTPUT_DIR s3://<bucket-name>/processed/"
echo "3. Sync Bedrock Knowledge Base"
