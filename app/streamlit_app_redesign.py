import streamlit as st
import sys
import os
import base64
from pathlib import Path

sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

try:
    from persona_bot_fast import FastPersonaBot
    from response_cache import CachedPersonaBot
    HAS_FAST_BOT = True
except ImportError:
    HAS_FAST_BOT = False

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

try:
    from portfolio_images import PortfolioImageHandler
    HAS_PORTFOLIO_IMAGES = True
except ImportError:
    HAS_PORTFOLIO_IMAGES = False

try:
    from canvas_assignments import get_upcoming_assignment, build_homework_help_prompt
    HAS_CANVAS = True
except ImportError:
    HAS_CANVAS = False

# Canvas course ID mapping
CANVAS_COURSE_MAP = {
    "COMMLD 515 - Advanced User Design": os.environ.get("CANVAS_COURSE_ID_515", "1892213"),
    "COMMLD 512 - UX Research & Strategy": os.environ.get("CANVAS_COURSE_ID_512", "1828126"),
}


def _verbosity_instruction(verbosity: str, lang: str) -> str:
    """Prepended to student message; lang is 'en' or 'zh'."""
    if lang == "zh":
        m = {
            "brief": "请用简短、精炼的中文回答（约2-3句）。直接具体。",
            "normal": "请用清晰、口语化的中文作答，并结合课程材料中的实例。",
            "detailed": "请用中文全面作答，包含具体例子、方法论，并引用课程材料与作品集相关内容。",
        }
    else:
        m = {
            "brief": "Provide a brief, concise response (2-3 sentences). Be direct and specific.",
            "normal": "Provide a clear, conversational response with relevant examples from the course materials.",
            "detailed": "Provide a comprehensive response with specific examples, methodologies, and references to course materials and portfolio work.",
        }
    return m.get(verbosity, m["normal"])


def get_base64_image(image_path):
    """Convert image to base64 for embedding in CSS/HTML"""
    try:
        with open(image_path, "rb") as f:
            data = base64.b64encode(f.read()).decode()
            print(f"✓ Loaded image: {image_path}")
            return data
    except Exception as e:
        print(f"✗ Error loading image {image_path}: {e}")
        return ""


# Removed - replaced with render_smart_follow_ups


def _clean_relevance(text: str) -> str:
    """Strip meta-phrases from relevance to get a clean topic statement."""
    if not text:
        return ""
    # Remove common meta-prefixes
    for prefix in (
        "The answer discusses ", "The entire answer is focused on ",
        "This relates to ", "The answer explains ", "The response covers ",
        "The answer covers ", "This concept is relevant because "
    ):
        if text.lower().startswith(prefix.lower()):
            text = text[len(prefix):].strip()
            break
    return text[:80].strip()


def render_smart_follow_ups(cards: dict, message_idx: int):
    """Render top 3 most relevant follow-up topics (80%+ confidence) with new format"""
    if not cards:
        return

    lang = st.session_state.get("ui_language", "en")
    
    # Get smart follow-ups from card generator
    # For now, manually filter and mix (will integrate with generator later)
    all_topics = []
    
    # Add teaching concepts with 80%+ confidence
    for concept in cards.get('teaching_concepts', []):
        if concept.get('confidence', 0) >= 0.80:
            # Use statement (new) or clean relevance (legacy): topic + short direct statement
            statement = concept.get('statement') or _clean_relevance(concept.get('relevance', ''))
            statement = (statement[:80] + '...') if len(statement) > 80 else statement
            if lang == "zh":
                fq = f"请更详细地讲解「{concept['concept']}」。"
            else:
                fq = f"Can you explain {concept['concept']} in more detail?"
            
            all_topics.append({
                'type': 'concept',
                'title': concept['concept'],
                'summary': statement,
                'prompt': fq,
                'confidence': concept.get('confidence', 0.85)
            })
    
    # Add portfolio examples with 80%+ confidence
    for project in cards.get('portfolio_examples', []):
        if project.get('confidence', 0) >= 0.80:
            project_name = project['title'].replace('-', ' ').title()
            # Use pre-built statement from generator, or derive from reasons
            summary = project.get('statement')
            if not summary:
                reasons = project.get('reasons', [])
                best = next((r for r in reasons if "demonstrates" in r.lower() or "shows" in r.lower() or "example of" in r.lower()), reasons[0] if reasons else "")
                summary = (best if len(best) <= 60 else best[:57] + "...") if best else "Real-world application example"
            if lang == "zh":
                pq = f"请多介绍一下「{project_name}」这个案例。"
                ptitle = f"{project_name} 案例"
                if summary == "Real-world application example":
                    summary = "实际应用示例"
            else:
                pq = f"Tell me more about the {project_name} example"
                ptitle = f"{project_name} example"
            
            all_topics.append({
                'type': 'example',
                'title': ptitle,
                'summary': summary,
                'prompt': pq,
                'confidence': project.get('confidence', 0.80)
            })
    
    # Sort by confidence and get top 3
    all_topics.sort(key=lambda x: x['confidence'], reverse=True)
    top_3 = all_topics[:3]
    
    if not top_3:
        return
    
    # Render new format
    _rel_title = "相关拓展：" if lang == "zh" else "Explore Related Topics:"
    st.markdown(f"""
    <div class="follow-up-section">
        <div class="follow-up-title"><strong>{_rel_title}</strong></div>
        <hr class="follow-up-divider">
    </div>
    """, unsafe_allow_html=True)
    
    # Create buttons in columns - no hover effects
    cols = st.columns(len(top_3))
    for idx, topic in enumerate(top_3):
        with cols[idx]:
            # Clean button label without markdown, with proper line break
            button_label = f"{topic['title']}\n{topic['summary']}"
            if st.button(
                button_label,
                key=f"followup_{message_idx}_{idx}",
                use_container_width=True
            ):
                # Store prompt for auto-submit
                st.session_state.pending_question = topic['prompt']
                st.rerun()


def render_learning_cards(cards: dict, message_idx: int):
    """Render smart follow-ups only (replaced old card system)"""
    render_smart_follow_ups(cards, message_idx)


# Old card rendering functions removed - replaced with smart follow-ups


st.set_page_config(
    page_title="UW Lecture Bot",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="collapsed"
)

# Load images as base64
# Try multiple paths for local vs Streamlit Cloud
import os
data_dir = os.path.join(os.path.dirname(__file__), '..', 'data')
if not os.path.exists(data_dir):
    data_dir = 'data'  # Streamlit Cloud path

print(f"Looking for images in: {data_dir}")
print(f"Background exists: {os.path.exists(os.path.join(data_dir, 'uw-background.png'))}")
print(f"Logo exists: {os.path.exists(os.path.join(data_dir, 'uw-logo.png'))}")

bg_image = get_base64_image(os.path.join(data_dir, "uw-background.png"))
logo_image = get_base64_image(os.path.join(data_dir, "uw-logo.png"))

st.markdown(f"""
<style>
    /* New UW Background */
    .stApp {{
        {"background-image: url('data:image/png;base64," + bg_image + "');" if bg_image else "background: linear-gradient(135deg, #4b2e83 0%, #2f1654 100%);"}
        background-size: cover;
        background-position: center;
        background-attachment: fixed;
    }}
    
    .main .block-container {{
        padding-top: 100px !important;
        max-width: 1200px !important;
        margin: 0 auto;
    }}
    
    /* Hide Streamlit branding */
    #MainMenu {{visibility: hidden;}}
    footer {{visibility: hidden;}}
    header {{visibility: hidden;}}
    
    /* White text over purple background */
    .stApp, .stMarkdown, p, span, div, label, h1, h2, h3 {{
        color: white !important;
    }}
    
    /* Sticky Navigation Bar */
    .top-nav {{
        position: fixed;
        top: 0;
        left: 0;
        right: 0;
        background: #34006f;
        padding: 12px 30px;
        display: flex;
        justify-content: space-between;
        align-items: center;
        z-index: 9999;
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.4);
    }}
    
    .nav-logo {{
        height: 50px;
    }}
    
    .nav-controls {{
        display: flex;
        gap: 20px;
        align-items: center;
    }}
</style>
""", unsafe_allow_html=True)

st.markdown("""
<style>
    /* Button styling - Simple text underline on hover */
    .stButton > button,
    .stButton button,
    button[kind="secondary"],
    button[kind="primary"] {
        background: rgba(255, 255, 255, 0.15) !important;
        border: 2px solid rgba(255, 255, 255, 0.3) !important;
        color: white !important;
        border-radius: 8px !important;
        padding: 8px 16px !important;
        box-shadow: none !important;
        transform: none !important;
        transition: none !important;
        pointer-events: auto !important;
        text-decoration: none !important;
    }
    
    .stButton > button:hover,
    .stButton button:hover,
    button[kind="secondary"]:hover,
    button[kind="primary"]:hover {
        background: rgba(255, 255, 255, 0.15) !important;
        border: 2px solid rgba(255, 255, 255, 0.3) !important;
        box-shadow: none !important;
        transform: none !important;
        text-decoration: underline !important;
    }
    
    .stButton > button:active,
    .stButton > button:focus,
    .stButton > button:focus:not(:active),
    .stButton > button:focus-visible,
    .stButton button:active,
    .stButton button:focus,
    .stButton button:focus:not(:active),
    .stButton button:focus-visible,
    button[kind="secondary"]:active,
    button[kind="secondary"]:focus,
    button[kind="secondary"]:focus-visible,
    button[kind="primary"]:active,
    button[kind="primary"]:focus,
    button[kind="primary"]:focus-visible {
        background: rgba(255, 255, 255, 0.15) !important;
        border: 2px solid rgba(255, 255, 255, 0.3) !important;
        box-shadow: none !important;
        outline: none !important;
        transform: none !important;
        text-decoration: none !important;
    }
    
    /* Kill any pseudo-elements that might create white boxes */
    .stButton > button::before,
    .stButton > button::after,
    .stButton button::before,
    .stButton button::after {
        display: none !important;
        content: none !important;
        background: none !important;
        opacity: 0 !important;
    }
    
    /* Override any Streamlit base styles */
    button[data-baseweb="button"],
    button[data-testid*="button"] {
        background-color: rgba(255, 255, 255, 0.15) !important;
    }
    
    button[data-baseweb="button"]:hover,
    button[data-testid*="button"]:hover {
        background-color: rgba(255, 255, 255, 0.15) !important;
        border-color: rgba(255, 255, 255, 0.3) !important;
    }
    }
    
    /* Input styling */
    .stTextInput input, .stSelectbox select {
        background: rgba(255, 255, 255, 0.1) !important;
        color: white !important;
        border: 1px solid rgba(255, 255, 255, 0.3) !important;
        border-radius: 8px !important;
    }
    
    .stTextInput input::placeholder {
        color: rgba(255, 255, 255, 0.5) !important;
    }
    
    /* Chat input footer - transparent background */
    section[data-testid="stBottom"],
    .stChatFloatingInputContainer {
        background: transparent !important;
        background-color: transparent !important;
    }
    
    /* Chat input field - white border, dark background, proper padding */
    [data-testid="stChatInput"] textarea,
    [data-testid="stChatInput"] input {
        background: rgba(40, 40, 40, 0.85) !important;
        border: 2px solid white !important;
        border-radius: 24px !important;
        color: white !important;
        padding: 12px 20px !important;
        backdrop-filter: blur(10px);
        caret-color: white !important;
    }
    
    [data-testid="stChatInput"] textarea::placeholder,
    [data-testid="stChatInput"] input::placeholder {
        color: rgba(255, 255, 255, 0.7) !important;
    }
    
    /* Audio player styling - integrate with bot bubble, limit width */
    .stAudio {
        margin: 12px 0 0 0 !important;
        background: transparent !important;
        max-width: 25% !important;
    }
    
    audio {
        width: 100% !important;
        max-width: 100% !important;
        height: 40px !important;
        background: rgba(0, 0, 0, 0.3) !important;
        border-radius: 8px !important;
    }
    
    /* User message bubble - purple gradient matching palette */
    .user-message {
        background: linear-gradient(135deg, #8938f6 0%, #b565ff 100%);
        color: white;
        padding: 12px 16px;
        border-radius: 18px;
        margin: 8px 0;
        max-width: 70%;
        margin-left: auto;
        margin-right: 0;
        word-wrap: break-word;
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
    }
    
    /* Bot message bubble - BLACK with subtle gradient */
    .bot-message {
        background: linear-gradient(135deg, rgba(15, 15, 15, 0.95) 0%, rgba(45, 45, 45, 0.95) 100%);
        color: white;
        padding: 16px;
        border-radius: 18px;
        margin: 8px 0 4px 0;
        max-width: 70%;
        margin-right: auto;
        margin-left: 0;
        word-wrap: break-word;
        border: 1px solid rgba(255, 255, 255, 0.1);
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
    }
    
    /* Audio player - styled to match bot bubble */
    .bot-message + div .stAudio,
    div:has(> .bot-message) + div .stAudio {
        background: linear-gradient(135deg, rgba(15, 15, 15, 0.95) 0%, rgba(45, 45, 45, 0.95) 100%);
        padding: 12px 16px;
        border-radius: 18px;
        margin: 0 0 8px 0;
        max-width: 70%;
        border: 1px solid rgba(255, 255, 255, 0.1);
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.3);
    }
    
    /* Follow-up prompt buttons */
    .followup-container {
        margin: 15px 0;
        display: flex;
        gap: 10px;
        flex-wrap: wrap;
    }
    
    .followup-button {
        background: transparent;
        border: 2px solid rgba(255, 255, 255, 0.4);
        color: white;
        padding: 8px 14px;
        border-radius: 20px;
        font-size: 13px;
        cursor: pointer;
        transition: all 0.2s;
    }
    
    .followup-button:hover {
        background: rgba(255, 255, 255, 0.15);
        border-color: rgba(255, 255, 255, 0.6);
    }
    
    /* Welcome message */
    .welcome-text {
        background: rgba(255, 255, 255, 0.15);
        border: 1px solid rgba(255, 255, 255, 0.3);
        border-radius: 12px;
        padding: 30px;
        margin: 40px auto;
        text-align: center !important;
        backdrop-filter: blur(10px);
        max-width: 800px;
    }
    
    .welcome-text h2 {
        margin-bottom: 15px;
        text-align: center !important;
    }
    
    .welcome-text p {
        text-align: center !important;
    }
    
    .welcome-text ul {
        text-align: left;
        display: inline-block;
        margin: 15px auto;
    }
    
    /* Expander styling */
    .streamlit-expanderHeader {
        background: rgba(255, 255, 255, 0.1) !important;
        color: white !important;
        border-radius: 8px;
    }
    
    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background: linear-gradient(180deg, rgba(51, 0, 111, 0.95) 0%, rgba(75, 0, 130, 0.95) 100%);
    }
    
    [data-testid="stSidebar"] * {
        color: white !important;
    }
    
    /* Follow-up Topics Styling */
    .follow-up-section {
        margin: 25px 0 15px 0;
    }
    
    .follow-up-title {
        font-size: 18px;
        color: white;
        margin-bottom: 10px;
        text-align: center;
    }
    
    .follow-up-divider {
        border: none;
        border-top: 2px solid rgba(255, 255, 255, 0.4);
        margin: 10px 0 20px 0;
    }
    
    .concept-item {
        background: rgba(255, 255, 255, 0.08);
        border-radius: 8px;
        border-left: 3px solid #9D4EDD;
        cursor: pointer;
        transition: all 0.2s;
    }
    
    .concept-item:hover {
        background: rgba(255, 255, 255, 0.12);
        border-left-color: #E0B0FF;
    }
    
    .concept-name {
        font-weight: 500;
        color: white;
        margin-bottom: 4px;
    }
    
    .concept-description {
        font-size: 13px;
        color: rgba(255, 255, 255, 0.8);
        line-height: 1.4;
    }
    
    .portfolio-project {
        padding: 12px;
        margin: 10px 0;
        background: rgba(255, 255, 255, 0.08);
        border-radius: 8px;
        border: 1px solid rgba(255, 255, 255, 0.15);
    }
    
    .portfolio-title {
        font-weight: 600;
        color: white;
        margin-bottom: 6px;
    }
    
    .portfolio-reason {
        font-size: 13px;
        color: rgba(255, 255, 255, 0.7);
        margin-bottom: 8px;
    }
    
    .portfolio-images {
        display: flex;
        gap: 10px;
        flex-wrap: wrap;
        margin-top: 10px;
    }
    
    .portfolio-image-thumb {
        width: 80px;
        height: 80px;
        object-fit: cover;
        border-radius: 6px;
        border: 2px solid rgba(255, 255, 255, 0.2);
        cursor: pointer;
        transition: all 0.2s;
    }
    
    .portfolio-image-thumb:hover {
        border-color: #9D4EDD;
        transform: scale(1.05);
    }
    
    .learn-more-btn {
        display: inline-block;
        padding: 6px 12px;
        margin-top: 8px;
        background: rgba(123, 47, 255, 0.3);
        border: 1px solid rgba(123, 47, 255, 0.5);
        border-radius: 6px;
        color: white;
        font-size: 13px;
        cursor: pointer;
        transition: all 0.2s;
    }
    
    .learn-more-btn:hover {
        background: rgba(123, 47, 255, 0.5);
        border-color: rgba(123, 47, 255, 0.8);
    }
    
    .expanded-content {
        margin-top: 10px;
        padding: 12px;
        background: rgba(0, 0, 0, 0.2);
        border-radius: 6px;
        font-size: 14px;
        line-height: 1.6;
    }

</style>
""", unsafe_allow_html=True)

# Initialize session state
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'kb_id' not in st.session_state:
    st.session_state.kb_id = "HHYCUJH32J"  # single shared KB for lecture-bot + ppmg
if 'bot' not in st.session_state:
    st.session_state.bot = None
if 'voice_enabled' not in st.session_state:
    st.session_state.voice_enabled = True
if 'audio_autoplay' not in st.session_state:
    st.session_state.audio_autoplay = False
if 'verbosity' not in st.session_state:
    st.session_state.verbosity = "normal"
if 'ui_language' not in st.session_state:
    st.session_state.ui_language = "en"  # "en" | "zh" — response + UI hints
if 'voice_generator' not in st.session_state:
    if HAS_VOICE:
        try:
            st.session_state.voice_generator = VoiceGenerator()
        except:
            st.session_state.voice_generator = None
    else:
        st.session_state.voice_generator = None
if 'pending_question' not in st.session_state:
    st.session_state.pending_question = None
if 'shown_projects' not in st.session_state:
    st.session_state.shown_projects = []  # Track recently shown portfolio examples
if 'upcoming_assignment' not in st.session_state:
    st.session_state.upcoming_assignment = None
if 'homework_help_mode' not in st.session_state:
    st.session_state.homework_help_mode = False
if 'portfolio_handler' not in st.session_state:
    if HAS_PORTFOLIO_IMAGES:
        try:
            st.session_state.portfolio_handler = PortfolioImageHandler()
        except:
            st.session_state.portfolio_handler = None
    else:
        st.session_state.portfolio_handler = None

# Auto-connect (use FastPersonaBot with ppmg KB for best performance)
if st.session_state.bot is None and HAS_FAST_BOT:
    try:
        fast_bot = FastPersonaBot(
            st.session_state.kb_id,
            "us.anthropic.claude-sonnet-4-20250514-v1:0",
            persona_name="Professor Levine",
        )
        st.session_state.bot = CachedPersonaBot(fast_bot, cache_ttl_hours=24)
    except Exception as e:
        if HAS_PERSONA_BOT:
            try:
                st.session_state.bot = PersonaBot(st.session_state.kb_id, "anthropic.claude-3-sonnet-20240229-v1:0")
            except:
                pass

# Top Navigation Bar with language toggle
_lang = st.session_state.ui_language
_en_style = "background:rgba(255,255,255,0.9);color:#34006f;font-weight:700;" if _lang == "en" else "background:transparent;color:rgba(255,255,255,0.6);"
_zh_style = "background:rgba(255,255,255,0.9);color:#34006f;font-weight:700;" if _lang == "zh" else "background:transparent;color:rgba(255,255,255,0.6);"
_lang_buttons = f"""
<div class="nav-controls">
    <a href="?lang=en" target="_self" class="lang-btn" style="{_en_style}">EN</a>
    <a href="?lang=zh" target="_self" class="lang-btn" style="{_zh_style}">中文</a>
</div>
"""

if logo_image:
    st.markdown(f"""
    <style>
    .lang-btn {{
        display:inline-block; padding:4px 12px; border-radius:4px;
        font-size:12px; text-decoration:none; border:1px solid rgba(255,255,255,0.4);
        margin-left:6px; transition:opacity 0.2s;
    }}
    .lang-btn:hover {{ opacity:0.8; }}
    </style>
    <div class="top-nav">
        <img src="data:image/png;base64,{logo_image}" class="nav-logo" alt="UW Logo">
        {_lang_buttons}
    </div>
    """, unsafe_allow_html=True)
else:
    st.markdown(f"""
    <style>
    .lang-btn {{
        display:inline-block; padding:4px 12px; border-radius:4px;
        font-size:12px; text-decoration:none; border:1px solid rgba(255,255,255,0.4);
        margin-left:6px; transition:opacity 0.2s;
    }}
    .lang-btn:hover {{ opacity:0.8; }}
    </style>
    <div class="top-nav">
        <div style="font-size: 24px; font-weight: bold;">UW Lecture Bot</div>
        {_lang_buttons}
    </div>
    """, unsafe_allow_html=True)

# Handle language switch via query param
_params = st.query_params
if _params.get("lang") in ("en", "zh"):
    if st.session_state.ui_language != _params["lang"]:
        st.session_state.ui_language = _params["lang"]
        st.query_params.clear()
        st.rerun()
    else:
        st.query_params.clear()

# Sidebar Settings
with st.sidebar:
    st.title("⚙️ Settings")
    
    st.markdown("### Course")
    course = st.selectbox(
        "Select Course",
        ["COMMLD 515 - Advanced User Design", "COMMLD 512 - UX Research & Strategy"],
        key="course",
        label_visibility="collapsed"
    )
    
    st.markdown("### Knowledge Base")
    st.caption("HHYCUJH32J (shared)")
    st.session_state.kb_id = "HHYCUJH32J"

    st.markdown("### Model")
    model_id = st.selectbox(
        "Select Model",
        [
            "us.anthropic.claude-sonnet-4-20250514-v1:0",
            "anthropic.claude-3-sonnet-20240229-v1:0",
            "anthropic.claude-3-haiku-20240307-v1:0",
            "anthropic.claude-3-5-sonnet-20240620-v1:0"
        ],
        key="model",
        label_visibility="collapsed"
    )
    
    st.markdown("### Voice")
    voice_enabled = st.toggle("Enable Voice", value=st.session_state.voice_enabled, key="voice_toggle")
    st.session_state.voice_enabled = voice_enabled
    
    audio_autoplay = st.toggle("🔊 Auto-play Audio", value=st.session_state.get('audio_autoplay', False), key="audio_autoplay_toggle")
    st.session_state.audio_autoplay = audio_autoplay
    
    st.markdown("### Response Length")
    st.caption("Controls how detailed responses are")
    
    col1, col2, col3 = st.columns(3)
    with col1:
        if st.button("Brief", key="brief_btn", use_container_width=True, type="primary" if st.session_state.verbosity == "brief" else "secondary"):
            st.session_state.verbosity = "brief"
    with col2:
        if st.button("Normal", key="normal_btn", use_container_width=True, type="primary" if st.session_state.verbosity == "normal" else "secondary"):
            st.session_state.verbosity = "normal"
    with col3:
        if st.button("Detailed", key="detailed_btn", use_container_width=True, type="primary" if st.session_state.verbosity == "detailed" else "secondary"):
            st.session_state.verbosity = "detailed"
    
    st.divider()
    
    if st.button("Reconnect Bot", type="primary", use_container_width=True):
        if HAS_FAST_BOT:
            try:
                fast_bot = FastPersonaBot(
                    st.session_state.kb_id, model_id,
                    persona_name="Professor Levine",
                    use_haiku=(model_id and "haiku" in model_id.lower())
                )
                st.session_state.bot = CachedPersonaBot(fast_bot, cache_ttl_hours=24)
                st.success("✓ Connected!")
            except Exception as e:
                if HAS_PERSONA_BOT:
                    try:
                        st.session_state.bot = PersonaBot(st.session_state.kb_id, model_id)
                        st.success("✓ Connected (fallback bot)")
                    except Exception as e2:
                        st.error(f"Error: {e2}")
                else:
                    st.error(f"Error: {e}")
        elif HAS_PERSONA_BOT:
            try:
                st.session_state.bot = PersonaBot(st.session_state.kb_id, model_id)
                st.success("✓ Connected!")
            except Exception as e:
                st.error(f"Error: {e}")

# Process chat input BEFORE display (avoids st.rerun() which clears chat in Streamlit 1.35+)

# --- Fetch upcoming assignment from Canvas ---
if HAS_CANVAS and 'course' in st.session_state:
    _canvas_course_id = CANVAS_COURSE_MAP.get(st.session_state.get("course", ""), "")
    if _canvas_course_id and st.session_state.upcoming_assignment is None:
        try:
            st.session_state.upcoming_assignment = get_upcoming_assignment(_canvas_course_id)
        except Exception as e:
            print(f"⚠ Canvas fetch failed: {e}")
            st.session_state.upcoming_assignment = False  # sentinel: tried and failed

_chat_placeholder = (
    "向 Levine 教授提问…"
    if st.session_state.ui_language == "zh"
    else "Ask Professor Levine..."
)
question = st.chat_input(_chat_placeholder)

if question and st.session_state.bot:
    _think = (
        "教授正在思考…"
        if st.session_state.ui_language == "zh"
        else "Professor Levine is thinking..."
    )
    with st.spinner(_think):
        try:
            _upcoming = st.session_state.get("upcoming_assignment")
            _hw_mode = st.session_state.get("homework_help_mode", False)

            if _hw_mode and _upcoming and isinstance(_upcoming, dict) and HAS_CANVAS:
                # Homework help mode: use rubric-grounded prompt
                hw_prompt = build_homework_help_prompt(
                    _upcoming, question, st.session_state.ui_language
                )
                result = st.session_state.bot.query(
                    hw_prompt,
                    use_persona=True,
                    response_language=st.session_state.ui_language,
                )
            else:
                _verb = _verbosity_instruction(
                    st.session_state.verbosity, st.session_state.ui_language
                )
                modified_question = f"{_verb} {question}"
                result = st.session_state.bot.query(
                    modified_question,
                    use_persona=True,
                    response_language=st.session_state.ui_language,
                )
            result['question'] = question
            if result.get('learning_cards', {}).get('portfolio_examples'):
                for project in result['learning_cards']['portfolio_examples']:
                    project_key = project.get('project_key')
                    if project_key and project_key not in st.session_state.shown_projects:
                        st.session_state.shown_projects.append(project_key)
                        if len(st.session_state.shown_projects) > 5:
                            st.session_state.shown_projects.pop(0)
            # English voice model; skip TTS for Chinese answers
            if (
                st.session_state.ui_language == "en"
                and st.session_state.voice_enabled
                and st.session_state.voice_generator
            ):
                try:
                    result['audio_base64'] = st.session_state.voice_generator.generate_audio_base64(
                        result['answer'], voice="chris"
                    )
                except Exception:
                    pass
            st.session_state.chat_history.append(result)
        except Exception as e:
            st.error(f"Error: {e}")

# Handle pending question from follow-up button (before display)
if st.session_state.pending_question:
    q = st.session_state.pending_question
    st.session_state.pending_question = None
    if st.session_state.bot:
        _think2 = (
            "教授正在思考…"
            if st.session_state.ui_language == "zh"
            else "Professor Levine is thinking..."
        )
        with st.spinner(_think2):
            try:
                _upcoming2 = st.session_state.get("upcoming_assignment")
                _hw_mode2 = st.session_state.get("homework_help_mode", False)

                if _hw_mode2 and _upcoming2 and isinstance(_upcoming2, dict) and HAS_CANVAS:
                    hw_prompt2 = build_homework_help_prompt(
                        _upcoming2, q, st.session_state.ui_language
                    )
                    result = st.session_state.bot.query(
                        hw_prompt2,
                        use_persona=True,
                        response_language=st.session_state.ui_language,
                    )
                else:
                    _verb2 = _verbosity_instruction(
                        st.session_state.verbosity, st.session_state.ui_language
                    )
                    modified_question = f"{_verb2} {q}"
                    result = st.session_state.bot.query(
                        modified_question,
                        use_persona=True,
                        response_language=st.session_state.ui_language,
                    )
                result['question'] = q
                if result.get('learning_cards', {}).get('portfolio_examples'):
                    for project in result['learning_cards']['portfolio_examples']:
                        project_key = project.get('project_key')
                        if project_key and project_key not in st.session_state.shown_projects:
                            st.session_state.shown_projects.append(project_key)
                            if len(st.session_state.shown_projects) > 5:
                                st.session_state.shown_projects.pop(0)
                if (
                    st.session_state.ui_language == "en"
                    and st.session_state.voice_enabled
                    and st.session_state.voice_generator
                ):
                    try:
                        result['audio_base64'] = st.session_state.voice_generator.generate_audio_base64(
                            result['answer'], voice="chris"
                        )
                    except Exception:
                        pass
                st.session_state.chat_history.append(result)
            except Exception as e:
                st.error(f"Error: {e}")

# Welcome message if no chat history
if not st.session_state.chat_history:
    st.markdown("""
    <div class="welcome-text">
        <h2>Welcome to Lecture Bot!</h2>
        <p>I'm Professor Levine's AI assistant, based on 100+ hours of lecture material. I can help you with:</p>
        <ul>
            <li>Course content and lecture materials</li>
            <li>UX design principles and methodologies</li>
            <li>Assignment guidance and clarification</li>
            <li>Portfolio examples and case studies</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

    # --- Homework Help button for upcoming assignment (below intro) ---
    _upcoming = st.session_state.get("upcoming_assignment")
    if _upcoming and isinstance(_upcoming, dict):
        _hw_label = (
            f"📝 {_upcoming['name']} 作业帮助"
            if st.session_state.ui_language == "zh"
            else f"📝 {_upcoming['name']} Homework Help"
        )
        _hw_due = (
            f"截止：{_upcoming['due_display']}"
            if st.session_state.ui_language == "zh"
            else f"Due: {_upcoming['due_display']}"
        )
        st.markdown(f"""
        <div style="background:rgba(255,255,255,0.10); border:1px solid rgba(255,255,255,0.25);
                    border-radius:10px; padding:12px 18px; max-width:500px; margin:10px auto;">
            <p style="margin:0; font-size:13px; font-weight:600; color:white;">📝 Upcoming Assignment</p>
            <p style="margin:2px 0 0; font-size:15px; font-weight:700; color:white;">{_upcoming['name']}</p>
            <p style="margin:2px 0 8px; font-size:12px; opacity:0.7; color:white;">{_hw_due} · {_upcoming['points']} pts</p>
        </div>
        """, unsafe_allow_html=True)
        if st.button(_hw_label, key="hw_help_btn", use_container_width=False):
            st.session_state.homework_help_mode = True
            if st.session_state.ui_language == "zh":
                st.session_state.pending_question = f"我正在做「{_upcoming['name']}」这个作业。请帮我理解评分标准以及如何拿到高分。"
            else:
                st.session_state.pending_question = f"I'm working on the {_upcoming['name']} assignment. Can you help me understand the rubric and what I need to do to get a top score?"
            st.rerun()

# Display chat history
for idx, chat in enumerate(st.session_state.chat_history):
    # User message
    st.markdown(f'<div class="user-message">{chat["question"]}</div>', unsafe_allow_html=True)
    
    # Bot message
    st.markdown(f'<div class="bot-message">{chat["answer"]}</div>', unsafe_allow_html=True)
    
    # Audio player (will be styled to look integrated)
    if st.session_state.voice_enabled and chat.get('audio_base64'):
        st.audio(
            f"data:audio/mpeg;base64,{chat['audio_base64']}",
            format="audio/mpeg",
            autoplay=st.session_state.audio_autoplay
        )
    
    # Learning Cards (only for most recent message)
    if idx == len(st.session_state.chat_history) - 1 and chat.get('learning_cards'):
        render_learning_cards(chat['learning_cards'], idx)

if question and not st.session_state.bot:
    if st.session_state.ui_language == "zh":
        st.error("请先在侧边栏设置中连接机器人。")
    else:
        st.error("Please connect to the bot in the sidebar settings first!")
