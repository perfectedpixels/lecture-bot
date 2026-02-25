# Persona Bot - Quick Start

## What I Built For You

A chatbot that responds as Jason Levine, using:
- ✅ Your lecture transcripts from S3/Bedrock Knowledge Base
- ✅ Your complete professional background (25+ years, AWS, Indeed, Amazon, Virgin, etc.)
- ✅ Your teaching style and industry expertise
- ✅ Safety rules to protect privacy and maintain authenticity

## Current Status

**Interface Running**: `http://localhost:8501`

**5 Tabs Available:**
1. 🎓 **Chat** - Main persona chat with Professor Levine
2. 🧪 **Test Safety** - Test safety rules with pre-built scenarios
3. 🔧 **Preprocess** - Clean and prepare transcripts
4. 📄 **Reports** - Generate comprehensive reports
5. 📊 **Analysis** - Assignment feedback and concept analysis

## Safety Rules Implemented

### 1. Privacy Protection ✅
Blocks: phone, address, personal email, family info
Response: "I keep my personal contact information private..."

### 2. Inappropriate Content ✅
Blocks: hacking, cheating, illegal activities
Response: "Let's keep our conversation focused on learning..."

### 3. Confrontational Language ✅
Blocks: insults, hostile tone
Response: "I'm here to help you learn in a respectful environment..."

### 4. Authenticity ✅
- Only uses lecture content + verified professional background
- Doesn't fabricate experiences or embellish
- Acknowledges when information isn't available

## Professional Context Included

**Current Roles:**
- Head of UX, Agentic AI Experiences at AWS (2024-Present)
- Senior Affiliate Instructor at UW (2012-Present)

**Career Highlights:**
- AWS: 70+ products, $2.4B revenue (2019-2024)
- Indeed: 250M users, $350M revenue (2018-2019)
- Amazon.com: 4 brands, $850M GMS, US patent (2014-2018)
- Ramp Group: Global UX Director, 200+ team (2004-2014)
- Virgin: Creative Director, tripled sales (2002-2004, London)
- Flutter: 420% growth (2001-2002, London)
- Siegel+Gale: Lead IA (1998-2001, LA)

**Major Clients:**
GM, Microsoft, T-Mobile, Stanford, Novartis, GE Health, Roche, Bayer, VW, Toyota, Mercedes, Trulia, Match.com, American Express, and more

## How to Use

### Test the Persona (Without AWS Setup)

The interface is live, but to actually query:
1. You need AWS credentials configured
2. Deploy the infrastructure (CDK)
3. Create Bedrock Knowledge Base
4. Upload lecture transcripts
5. Enter Knowledge Base ID in sidebar

### Test Safety Rules Now

Go to the **🧪 Test Safety** tab to see:
- Pre-built test scenarios
- Which questions work vs. get blocked
- Custom test input
- Visual feedback on safety triggers

## Example Interactions

### ✅ Will Work
```
"What did you teach about user-centered design?"
"Tell me about your experience at AWS"
"How do you approach design thinking?"
"Can you review my assignment on prototyping?"
```

### 🛡️ Will Block
```
"What's your phone number?" → Privacy protection
"How can I cheat?" → Inappropriate content
"This course is stupid" → Confrontational language
```

## Next Steps

### To Make It Fully Functional:

1. **Configure AWS Credentials**
   ```bash
   aws configure
   # Enter your access key and secret
   ```

2. **Deploy Infrastructure**
   ```bash
   cd infrastructure
   npm install
   npm run build
   cdk deploy
   ```

3. **Create Bedrock Knowledge Base**
   - AWS Console → Bedrock → Knowledge Bases
   - Use S3 bucket from deployment
   - Note the Knowledge Base ID

4. **Upload Lecture Transcripts**
   ```bash
   ./scripts/upload_transcript.sh path/to/lecture.txt "Lecture_Name"
   ```

5. **Connect in Interface**
   - Enter Knowledge Base ID in sidebar
   - Click "Connect"
   - Start chatting!

## Files Created

**Core Bot:**
- `src/persona_bot_safe.py` - Main persona bot with safety rules
- `src/persona_bot.py` - Original version (still available)

**Interface:**
- `app/streamlit_app_simple.py` - Current running interface
- `app/streamlit_app.py` - Full-featured version

**Documentation:**
- `PERSONA_GUIDE.md` - Complete guide with all details
- `PERSONA_QUICK_START.md` - This file
- `jason_levine-cv.txt` - Your CV (source of professional context)

**Infrastructure:**
- `infrastructure/` - AWS CDK code
- `scripts/` - Helper scripts for upload and setup

## Testing Without Full Setup

You can explore the interface now at `http://localhost:8501`:
- See the layout and tabs
- Read the safety rules
- View the test scenarios
- Understand the workflow

The chat won't work until you complete the AWS setup, but you can see how everything is structured.

## Questions?

- Full details: See `PERSONA_GUIDE.md`
- Deployment: See `DEPLOYMENT.md` or `QUICKSTART.md`
- Architecture: See `ARCHITECTURE.md`
- Workflow: See `COMPLETE_WORKFLOW.md`
