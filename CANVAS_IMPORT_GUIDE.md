# Canvas Content Import Guide

How to import your Canvas course content into the Lecture Bot.

## Step 1: Export from Canvas

1. Go to your Canvas course
2. Settings → Export Course Content
3. Select "Course Content Export"
4. Click "Create Export"
5. Download the `.imscc` file when ready

## Step 2: Extract the Export

```bash
cd ~/Dropbox/playground/class\ projects

# Unzip Canvas export
unzip ~/Downloads/canvas_export.imscc -d data/canvas_raw

# See what's inside
ls -lh data/canvas_raw/
```

## Step 3: Extract Text Content Only

This filters out images, videos, and extracts clean text:

```bash
# Make script executable
chmod +x scripts/extract_canvas_content.py

# Extract text content
python3 scripts/extract_canvas_content.py data/canvas_raw --output data/canvas_extracted
```

**Output**: Clean text files in `data/canvas_extracted/`
- `page_*.txt` - Course pages
- `assignment_*.txt` - Assignment descriptions
- `discussion_*.txt` - Discussion prompts

**Size reduction**: 500MB → typically 1-5MB of text

## Step 4: Review Extracted Content

```bash
# See what was extracted
ls -lh data/canvas_extracted/

# Preview a file
head -20 data/canvas_extracted/page_week1_intro.txt
```

## Step 5: Upload to S3

### Option A: Upload All at Once

```bash
# Upload all extracted content
aws s3 sync data/canvas_extracted/ s3://lecture-transcripts-427791004700/canvas/ \
  --metadata "source=canvas,course=UX_Design"
```

### Option B: Upload Selectively

```bash
# Upload only assignments
aws s3 sync data/canvas_extracted/ s3://lecture-transcripts-427791004700/assignments/ \
  --exclude "*" --include "assignment_*"

# Upload only course pages
aws s3 sync data/canvas_extracted/ s3://lecture-transcripts-427791004700/lectures/ \
  --exclude "*" --include "page_*"
```

## Step 6: Sync Knowledge Base

1. Go to Bedrock Console → Knowledge Bases
2. Select `LectureBotStack-KB`
3. Go to "Data sources" tab
4. Click "Sync"
5. Wait 2-5 minutes

## Step 7: Test

Ask the bot:
- "What's covered in week 1?"
- "What are the requirements for assignment 2?"
- "Summarize the discussion on user research"

---

## What Gets Extracted

✅ **Included:**
- Course page text
- Assignment descriptions
- Discussion prompts
- Module descriptions
- Syllabus content

❌ **Excluded:**
- Images and videos (too large)
- Student submissions
- Grades and analytics
- Embedded files (PDFs, etc.)

---

## Troubleshooting

### Script Fails to Parse

Canvas export formats vary. If the script doesn't work:

**Manual approach:**
```bash
# Find HTML files
find data/canvas_raw -name "*.html" -type f

# Convert HTML to text manually
for file in data/canvas_raw/wiki_content/*.html; do
  # Use a simple HTML to text converter
  python3 -c "
from html.parser import HTMLParser
import sys

class TextExtractor(HTMLParser):
    def __init__(self):
        super().__init__()
        self.text = []
    def handle_data(self, data):
        if data.strip():
            self.text.append(data.strip())
    def get_text(self):
        return '\n'.join(self.text)

with open('$file', 'r') as f:
    parser = TextExtractor()
    parser.feed(f.read())
    print(parser.get_text())
" > "data/canvas_extracted/$(basename $file .html).txt"
done
```

### Files Too Large

If individual files are huge (>100KB):

```bash
# Split large files
split -b 50k data/canvas_extracted/large_file.txt data/canvas_extracted/large_file_part_
```

### Duplicate Content

Canvas exports sometimes duplicate content. Remove duplicates:

```bash
# Find duplicate files
fdupes -r data/canvas_extracted/
```

---

## Best Practices

1. **Review before uploading** - Check extracted files make sense
2. **Organize by type** - Separate assignments, lectures, discussions
3. **Add metadata** - Use S3 metadata for better organization
4. **Test incrementally** - Upload a few files first, test, then upload all
5. **Keep originals** - Don't delete the Canvas export

---

## Next Steps

After importing Canvas content:
1. Upload lecture transcripts (if separate)
2. Build affinity map for concept clustering
3. Test bot with course-specific questions
4. Deploy to EC2 for student access
