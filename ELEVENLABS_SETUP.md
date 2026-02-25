# ElevenLabs Voice Integration Setup

Add voice responses to your Lecture Bot using ElevenLabs text-to-speech API.

## Quick Setup

### 1. Get ElevenLabs API Key

1. Go to https://elevenlabs.io
2. Sign up or log in
3. Go to Profile → API Keys
4. Copy your API key

### 2. Set Environment Variable

Add to your `~/.zshrc` or `~/.bash_profile`:

```bash
export ELEVENLABS_API_KEY="your_api_key_here"
```

Then reload:
```bash
source ~/.zshrc
```

### 3. Install Dependencies

```bash
cd app
source venv/bin/activate
pip install requests
```

### 4. Test Voice Generation

```python
from src.voice_generator import VoiceGenerator

vg = VoiceGenerator()
audio = vg.generate_audio("Hello, this is a test", voice="chris")
print(f"Generated {len(audio)} bytes of audio")
```

## Using Voice in Streamlit

1. Start Streamlit: `streamlit run streamlit_app_simple.py`
2. Toggle "🔊 Voice" at the top of the page
3. Ask a question
4. Audio player appears with the response

## Voice Configuration

The bot uses the "Chris" voice by default. To change:

Edit `src/voice_generator.py`:
```python
self.voices = {
    "chris": "iP95p4xoKVk53GoZ742B",
    "your_voice": "voice_id_here"
}
```

Get voice IDs:
```python
vg = VoiceGenerator()
voices = vg.list_voices()
for voice in voices['voices']:
    print(f"{voice['name']}: {voice['voice_id']}")
```

## Features

- ✅ Toggle voice on/off
- ✅ Chris voice (professional male)
- ✅ HTML5 audio player with controls
- ✅ Volume control
- ✅ Mute/unmute
- ✅ Autoplay on new responses
- ✅ Audio persists in chat history

## Troubleshooting

**"ElevenLabs API key required"**
- Set `ELEVENLABS_API_KEY` environment variable
- Restart terminal and Streamlit

**"Voice generation failed"**
- Check API key is valid
- Verify you have ElevenLabs credits
- Check internet connection

**No audio plays**
- Check browser supports HTML5 audio
- Try different browser (Chrome, Firefox, Safari)
- Check browser audio isn't muted

## API Limits

Free tier: 10,000 characters/month
- ~100 responses (assuming 100 chars each)
- Upgrade at https://elevenlabs.io/pricing

## Cost Optimization

To reduce API calls:
1. Keep responses concise (already configured in persona)
2. Toggle voice off when not needed
3. Audio is cached in chat history (no re-generation)

## Advanced: Custom Voice Settings

Edit `src/voice_generator.py` to adjust:

```python
"voice_settings": {
    "stability": 0.5,        # 0-1, higher = more consistent
    "similarity_boost": 0.75  # 0-1, higher = closer to original
}
```

## Security Note

Never commit your API key to git! It's in `.gitignore` as an environment variable.
