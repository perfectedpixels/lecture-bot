import streamlit as st
import sys
import os
import time
import base64
from pathlib import Path

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

try:
    from persona_bot_safe import PersonaBot
    HAS_PERSONA_BOT = True
except ImportError:
    HAS_PERSONA_BOT = False

try:
    from voice_generator import VoiceGenerator
    HAS_VOICE = True
except ImportError:
    HAS_VOICE = False


def get_base64_image(image_path):
    """Convert image to base64 for embedding"""
    with open(image_path, "rb") as f:
        return base64.b64encode(f.read()).decode()


def render_smart_follow_ups(cards: dict, message_idx: int):
    """Render top 3 most relevant follow-up topics (80%+ confidence)"""
    if not cards:
        return
    
    # Combine all topics with confidence scores
    all_topics = []
    
    # Add teaching concepts
    for concept in cards.get('teaching_concepts', []):
        all_topics.append({
            'type': 'concept',
            'title': concept['concept'],
            'summary': concept.get('relevance', '')[:60],  # Max 10 words ~60 chars
            'prompt': f"Can you explain {concept['concept']} in more detail?",
            'confidence': concept.get('confidence', 0.85)
        })
    
    # Add portfolio examples
    for project in cards.get('portfolio_examples', []):
        project_name = project['title'].replace('-', ' ').title()
        reasons = project.get('reasons', [])
        summary = ' '.join(reasons[0].split()[:10]) if reasons else "Real-world example"
        
        all_topics.append({
            'type': 'example',
            'title': f"{project_name} work example",
            'summary': summary,
            'prompt': f"Tell me more about the {project_name} example",
            'confidence': project.get('confidence', 0.80)
        })
    
    # Filter by confidence and get top 3
    high_confidence = [t for t in all_topics if t['confidence'] >= 0.80]
    top_3 = sorted(high_confidence, key=lambda x: x['confidence'], reverse=True)[:3]
    
    if not top_3:
        return
    
    st.markdown("""
    <div class="follow-up-section">
        <div class="follow-up-title"><strong>Explore Related Topics:</strong></div>
        <hr class="follow-up-divider">
    </div>
    """, unsafe_allow_html=True)
    
    cols = st.columns(len(top_3))
    for idx, topic in enumerate(top_3):
        with cols[idx]:
            if st.button(
                f"**{topic['title']}**\n\n{topic['summary']}",
                key=f"followup_{message_idx}_{idx}",
                use_container_width=True
            ):
                # Auto-populate and submit
                st.session_state.auto_submit_text = topic['prompt']
                st.rerun()


st.set_page_config(
    page_title="UW Lecture Bot",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Get base64 encoded images
bg_image = get_base64_image("../data/uw-background.png")
logo_image = get_base64_image("../data/uw-logo.png")

st.markdown(f"""
<style>
    /* Background */
    .stApp {{
        background-image: url('data:image/png;base64,{bg_image}');
        background-size: cover;
        background-position: center;
        background-attachment: fixed;
    }}
    
    .main .block-container {{
        padding-top: 120px !important;
        max-width: 1200px !important;
        margin: 0 auto;
    }}
    
    /* Hide Streamlit branding */
    #MainMenu {{visibility: hidden;}}
    footer {{visibility: hidden;}}
    header {{visibility: hidden;}}
    
    /* White text */
    .stApp, .stMarkdown, p, span, div, label, h1, h2, h3 {{
        color: white !important;
    }}
    
    /* Top Navigation Bar */
    .top-nav {{
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        background: #34006f;
        padding: 15px 30px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        z-index: 9999;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    }}
    
    .nav-logo {{
        height: 50px;
    }}
    
    .nav-controls {{
        display: flex;
        gap: 20px;
        align-items: center;
    }}
    
    /* Logo (initial centered position) */
    .logo-container {{
        text-align: center;
        margin: 40px 0;
    }}
    
    .logo-container img {{
        max-width: 400px;
        width: 100%;
    }}
    
    /* Button styling - Simple border highlight on hover */
    .stButton button {
        background: rgba(255, 255, 255, 0.15) !important;
        border: 2px solid rgba(255, 255, 255, 0.3) !important;
        color: white !important;
        border-radius: 8px !important;
        padding: 12px 16px !important;
        transition: border-color 0.2s ease !important;
        text-align: left !important;
        box-shadow: none !important;
        transform: none !important;
    }
    
    .stButton button:hover {
        background: rgba(255, 255, 255, 0.15) !important;
        border: 2px solid rgba(255, 255, 255, 0.8) !important;
        box-shadow: none !important;
        transform: none !important;
    }
    
    .stButton button:active,
    .stButton button:focus {
        background: rgba(255, 255, 255, 0.15) !important;
        border: 2px solid rgba(255, 255, 255, 0.8) !important;
        box-shadow: none !important;
        outline: none !important;
        transform: none !important;
    }
    
    /* Remove any white overlays or pseudo-elements */
    .stButton button::before,
    .stButton button::after {
        display: none !important;
        content: none !important;
        background: none !important;
    }
    
    /* Override Streamlit's default button states */
    .stButton > button[data-baseweb="button"] {
        background-color: rgba(255, 255, 255, 0.15) !important;
    }
    
    .stButton > button[data-baseweb="button"]:hover {
        background-color: rgba(255, 255, 255, 0.25) !important;
    }
    
    /* Kill tooltips and overlays that cause layout shift */
    [role="tooltip"],
    .stTooltipIcon,
    [data-testid="stTooltipHoverTarget"],
    [data-baseweb="tooltip"] {
        display: none !important;
        visibility: hidden !important;
        opacity: 0 !important;
        pointer-events: none !important;
    }
    
    /* Prevent layout shift on hover */
    .stButton,
    .stButton > button {
        position: relative !important;
    }
    
    .stButton:hover,
    .stButton > button:hover {
        transform: none !important;
    }
    
    /* Chat input */
    [data-testid="stChatInput"] input {{
        background: rgba(40, 40, 40, 0.85) !important;
        border: 2px solid white !important;
        border-radius: 24px !important;
        color: white !important;
        padding: 12px 20px !important;
    }}
    
    /* User message bubble */
    .user-message {{
        background: linear-gradient(135deg, #7B2FFF 0%, #9D4EDD 100%);
        color: white;
        padding: 12px 16px;
        border-radius: 18px;
        margin: 8px 0;
        max-width: 70%;
        margin-left: auto;
        word-wrap: break-word;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
    }}
    
    /* Bot message bubble */
    .bot-message {{
        background: linear-gradient(135deg, rgba(51, 0, 111, 0.95) 0%, rgba(75, 0, 130, 0.95) 100%);
        color: white;
        padding: 12px 16px;
        border-radius: 18px;
        margin: 8px 0;
        max-width: 70%;
        word-wrap: break-word;
        border: 1px solid rgba(255, 255, 255, 0.15);
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
    }}
    
    /* Follow-up section */
    .follow-up-section {{
        margin: 20px 0;
    }}
    
    .follow-up-title {{
        font-size: 18px;
        color: white;
        margin-bottom: 10px;
    }}
    
    .follow-up-divider {{
        border: none;
        border-top: 2px solid rgba(255, 255, 255, 0.3);
        margin: 10px 0 20px 0;
    }}
    
    /* Welcome message */
    .welcome-text {{
        background: rgba(255, 255, 255, 0.15);
        border: 1px solid rgba(255, 255, 255, 0.3);
        border-radius: 12px;
        padding: 30px;
        margin: 40px 0;
        text-align: center;
        backdrop-filter: blur(10px);
    }}
    
    /* Sidebar */
    [data-testid="stSidebar"] {{
        background: linear-gradient(180deg, rgba(51, 0, 111, 0.95) 0%, rgba(75, 0, 130, 0.95) 100%);
    }}
    
    [data-testid="stSidebar"] * {{
        color: white !important;
    }}
    
    /* Audio player */
    .stAudio {{
        margin: 10px 0 !important;
    }}
    
    audio {{
        width: 100% !important;
        max-width: 400px !important;
    }}
</style>
""", unsafe_allow_html=True)

# Top Navigation
st.markdown(f"""
<div class="top-nav">
    <img src="data:image/png;base64,{logo_image}" class="nav-logo" alt="UW Logo">
    <div class="nav-controls">
        <span id="audio-toggle">🔊 Audio</span>
        <span id="settings-btn">⚙️ Settings</span>
    </div>
</div>
""", unsafe_allow_html=True)

# Initialize session state
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'kb_id' not in st.session_state:
    st.session_state.kb_id = "1TTBVE6MG2"
if 'bot' not in st.session_state:
    st.session_state.bot = None
if 'voice_enabled' not in st.session_state:
    st.session_state.voice_enabled = True
if 'audio_autoplay' not in st.session_state:
    st.session_state.audio_autoplay = True
if 'verbosity' not in st.session_state:
    st.session_state.verbosity = "normal"
if 'voice_generator' not in st.session_state:
    if HAS_VOICE:
        try:
            st.session_state.voice_generator = VoiceGenerator()
        except:
            st.session_state.voice_generator = None
    else:
        st.session_state.voice_generator = None
if 'auto_submit_text' not in st.session_state:
    st.session_state.auto_submit_text = None

# Auto-connect bot
if st.session_state.bot is None and HAS_PERSONA_BOT:
    try:
        st.session_state.bot = PersonaBot(st.session_state.kb_id, "anthropic.claude-3-sonnet-20240229-v1:0")
    except:
        pass

# Sidebar Settings
with st.sidebar:
    st.title("Settings")
    
    st.markdown("### Model")
    model_id = st.selectbox(
        "Select Claude Model",
        [
            "anthropic.claude-3-sonnet-20240229-v1:0",
            "anthropic.claude-3-haiku-20240307-v1:0",
            "anthropic.claude-3-5-sonnet-20240620-v1:0"
        ],
        key="model"
    )
    
    st.markdown("### Response Length")
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("Brief", use_container_width=True):
            st.session_state.verbosity = "brief"
    with col2:
        if st.button("Normal", use_container_width=True):
            st.session_state.verbosity = "normal"
    with col3:
        if st.button("Detailed", use_container_width=True):
            st.session_state.verbosity = "detailed"
    
    st.markdown("### Audio")
    st.session_state.audio_autoplay = st.toggle("Auto-play audio", value=st.session_state.audio_autoplay)

# Logo (will shrink on scroll - handled by JS)
st.markdown(f"""
<div class="logo-container">
    <img src="data:image/png;base64,{logo_image}" alt="University of Washington">
</div>
""", unsafe_allow_html=True)

# Welcome message
if not st.session_state.chat_history:
    st.markdown("""
    <div class="welcome-text">
        <h2>Welcome to the UW Lecture Bot</h2>
        <p>Ask me anything about the course content!</p>
    </div>
    """, unsafe_allow_html=True)

# Display chat history
for idx, msg in enumerate(st.session_state.chat_history):
    if msg['role'] == 'user':
        st.markdown(f'<div class="user-message">{msg["content"]}</div>', unsafe_allow_html=True)
    else:
        st.markdown(f'<div class="bot-message">{msg["content"]}</div>', unsafe_allow_html=True)
        
        # Audio if available
        if msg.get('audio'):
            if st.session_state.audio_autoplay:
                st.audio(msg['audio'], format='audio/mp3', autoplay=True)
            else:
                st.audio(msg['audio'], format='audio/mp3')
        
        # Smart follow-ups (only for most recent message)
        if idx == len(st.session_state.chat_history) - 1 and msg.get('cards'):
            render_smart_follow_ups(msg['cards'], idx)

# Handle auto-submit
if st.session_state.auto_submit_text:
    # Simulate typing animation (simplified for now)
    question = st.session_state.auto_submit_text
    st.session_state.auto_submit_text = None
    
    # Process immediately
    if st.session_state.bot:
        st.session_state.chat_history.append({"role": "user", "content": question})
        
        with st.spinner("Thinking..."):
            response = st.session_state.bot.query(
                question,
                verbosity=st.session_state.verbosity
            )
        
        msg_data = {"role": "assistant", "content": response['answer']}
        
        # Generate audio
        if st.session_state.voice_enabled and st.session_state.voice_generator:
            try:
                audio_data = st.session_state.voice_generator.generate(response['answer'])
                msg_data['audio'] = audio_data
            except:
                pass
        
        # Add cards
        if response.get('cards'):
            msg_data['cards'] = response['cards']
        
        st.session_state.chat_history.append(msg_data)
        st.rerun()

# Chat input
question = st.chat_input("Ask Professor Levine...")

if question and st.session_state.bot:
    st.session_state.chat_history.append({"role": "user", "content": question})
    
    with st.spinner("Thinking..."):
        response = st.session_state.bot.query(
            question,
            verbosity=st.session_state.verbosity
        )
    
    msg_data = {"role": "assistant", "content": response['answer']}
    
    # Generate audio
    if st.session_state.voice_enabled and st.session_state.voice_generator:
        try:
            audio_data = st.session_state.voice_generator.generate(response['answer'])
            msg_data['audio'] = audio_data
        except:
            pass
    
    # Add cards
    if response.get('cards'):
        msg_data['cards'] = response['cards']
    
    st.session_state.chat_history.append(msg_data)
    st.rerun()
elif question and not st.session_state.bot:
    st.error("Please configure AWS credentials in Streamlit Cloud secrets")
