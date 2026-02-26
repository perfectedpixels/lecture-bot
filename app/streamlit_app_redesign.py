import streamlit as st
import sys
import os
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

try:
    from portfolio_images import PortfolioImageHandler
    HAS_PORTFOLIO_IMAGES = True
except ImportError:
    HAS_PORTFOLIO_IMAGES = False


# Removed - replaced with render_smart_follow_ups


def render_smart_follow_ups(cards: dict, message_idx: int):
    """Render top 3 most relevant follow-up topics (80%+ confidence) with new format"""
    if not cards:
        return
    
    # Get smart follow-ups from card generator
    # For now, manually filter and mix (will integrate with generator later)
    all_topics = []
    
    # Add teaching concepts with 80%+ confidence
    for concept in cards.get('teaching_concepts', []):
        if concept.get('confidence', 0) >= 0.80:
            summary_words = concept.get('relevance', '').split()[:10]
            summary = ' '.join(summary_words)
            
            all_topics.append({
                'type': 'concept',
                'title': concept['concept'],
                'summary': summary,
                'prompt': f"Can you explain {concept['concept']} in more detail?",
                'confidence': concept.get('confidence', 0.85)
            })
    
    # Add portfolio examples with 80%+ confidence
    for project in cards.get('portfolio_examples', []):
        if project.get('confidence', 0) >= 0.80:
            project_name = project['title'].replace('-', ' ').title()
            reasons = project.get('reasons', [])
            summary_words = ' '.join(reasons).split()[:10] if reasons else "Real-world application example".split()
            summary = ' '.join(summary_words)
            
            all_topics.append({
                'type': 'example',
                'title': f"{project_name} work example",
                'summary': summary,
                'prompt': f"Tell me more about the {project_name} example",
                'confidence': project.get('confidence', 0.80)
            })
    
    # Sort by confidence and get top 3
    all_topics.sort(key=lambda x: x['confidence'], reverse=True)
    top_3 = all_topics[:3]
    
    if not top_3:
        return
    
    # Render new format
    st.markdown("""
    <div class="follow-up-section">
        <div class="follow-up-title"><strong>Explore Related Topics:</strong></div>
        <hr class="follow-up-divider">
    </div>
    """, unsafe_allow_html=True)
    
    # Create buttons in columns
    cols = st.columns(len(top_3))
    for idx, topic in enumerate(top_3):
        with cols[idx]:
            button_label = f"**{topic['title']}**\n\n{topic['summary']}"
            if st.button(
                button_label,
                key=f"followup_{message_idx}_{idx}",
                use_container_width=True,
                help=f"Confidence: {topic['confidence']:.0%}"
            ):
                # Store prompt for auto-submit
                st.session_state.pending_question = topic['prompt']
                st.rerun()


def render_learning_cards(cards: dict, message_idx: int):
    """Render smart follow-ups only (replaced old card system)"""
    render_smart_follow_ups(cards, message_idx)


# Old card rendering functions removed - replaced with smart follow-ups


st.set_page_config(
    page_title="Lecture Bot",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="collapsed"
)

st.markdown("""
<style>
    /* UW Purple Diagonal Background */
    .stApp {
        background-image: url('https://cdn.uconnectlabs.com/wp-content/uploads/sites/25/2021/01/UWBrand-PurpleDiagonal.jpg');
        background-size: cover;
        background-position: center;
        background-attachment: fixed;
    }
    
    .main .block-container {
        padding-top: 1rem !important;
        max-width: 1200px !important;
        margin: 0 auto;
    }
    
    /* Hide Streamlit branding */
    #MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    header {visibility: hidden;}
    
    /* White text over purple background */
    .stApp, .stMarkdown, p, span, div, label, h1, h2, h3 {
        color: white !important;
    }
    
    /* Header styling */
    .header-container {
        display: flex;
        justify-content: space-between;
        align-items: center;
        padding: 15px 20px;
        margin-bottom: 20px;
    }
    
    .header-title {
        font-size: 28px;
        font-weight: bold;
        color: white;
    }
    
    /* Button styling */
    .stButton button {
        background: rgba(255, 255, 255, 0.15) !important;
        border: 1px solid rgba(255, 255, 255, 0.3) !important;
        color: white !important;
        border-radius: 8px !important;
        padding: 8px 16px !important;
        transition: all 0.2s !important;
    }
    
    .stButton button:hover {
        background: rgba(255, 255, 255, 0.25) !important;
        border-color: rgba(255, 255, 255, 0.5) !important;
    }
    
    .stButton button:active,
    .stButton button:focus {
        background: rgba(255, 255, 255, 0.30) !important;
        border-color: rgba(255, 255, 255, 0.6) !important;
        box-shadow: none !important;
    }
    
    /* Override Streamlit's default button focus/active states */
    .stButton > button:focus:not(:active) {
        background: rgba(255, 255, 255, 0.25) !important;
        border-color: rgba(255, 255, 255, 0.5) !important;
        box-shadow: none !important;
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
    
    /* Chat input footer - transparent/invisible, floating text box */
    .stChatInputContainer,
    [data-testid="stChatInput"],
    [data-testid="stBottom"],
    section[data-testid="stBottom"],
    .stBottom,
    div[class*="stChatInput"],
    footer,
    section[data-testid="stChatFloatingInputContainer"],
    .stChatFloatingInputContainer {
        background: transparent !important;
        background-color: transparent !important;
        padding: 20px !important;
    }
    
    /* Target the input field itself - white border, semi-transparent dark background */
    [data-testid="stChatInput"] input,
    .stChatInput input,
    input[type="text"] {
        background: rgba(40, 40, 40, 0.85) !important;
        border: 2px solid white !important;
        border-radius: 24px !important;
        color: white !important;
        padding: 12px 20px 12px 50px !important;
        backdrop-filter: blur(10px);
        position: relative;
    }
    
    /* Purple triangle indicator to the left */
    [data-testid="stChatInput"]::before {
        content: "▶";
        position: absolute;
        left: 20px;
        top: 50%;
        transform: translateY(-50%);
        color: #7B2FFF;
        font-size: 20px;
        z-index: 10;
    }
    
    [data-testid="stChatInput"] input::placeholder,
    .stChatInput input::placeholder,
    input[type="text"]::placeholder {
        color: rgba(255, 255, 255, 0.7) !important;
    }
    
    /* Hide audio player by default, but show controls */
    .stAudio {
        margin: 10px 0 !important;
    }
    
    audio {
        width: 100% !important;
        max-width: 400px !important;
        height: 40px !important;
    }
    
    /* Remove waveform styles - not needed anymore */
    
    /* User message bubble - lighter purple */
    .user-message {
        background: linear-gradient(135deg, #7B2FFF 0%, #9D4EDD 100%);
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
    
    /* Bot message bubble - darker purple with border */
    .bot-message {
        background: linear-gradient(135deg, rgba(51, 0, 111, 0.95) 0%, rgba(75, 0, 130, 0.95) 100%);
        color: white;
        padding: 12px 16px;
        border-radius: 18px;
        margin: 8px 0;
        max-width: 70%;
        margin-right: auto;
        margin-left: 0;
        word-wrap: break-word;
        border: 1px solid rgba(255, 255, 255, 0.15);
        box-shadow: 0 2px 8px rgba(0, 0, 0, 0.2);
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
        background: rgba(255, 255, 255, 0.1);
        border: 1px solid rgba(255, 255, 255, 0.2);
        border-radius: 12px;
        padding: 30px;
        margin: 40px 0;
        text-align: center;
        backdrop-filter: blur(10px);
    }
    
    .welcome-text h2 {
        margin-bottom: 15px;
    }
    
    .welcome-text ul {
        text-align: left;
        display: inline-block;
        margin: 15px 0;
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
if 'pending_question' not in st.session_state:
    st.session_state.pending_question = None
if 'portfolio_handler' not in st.session_state:
    if HAS_PORTFOLIO_IMAGES:
        try:
            st.session_state.portfolio_handler = PortfolioImageHandler()
        except:
            st.session_state.portfolio_handler = None
    else:
        st.session_state.portfolio_handler = None

# Auto-connect
if st.session_state.bot is None and HAS_PERSONA_BOT:
    try:
        st.session_state.bot = PersonaBot(st.session_state.kb_id, "anthropic.claude-3-sonnet-20240229-v1:0")
    except:
        pass

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
    
    st.markdown("### Model")
    model_id = st.selectbox(
        "Select Model",
        [
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
    
    audio_autoplay = st.toggle("🔊 Auto-play Audio", value=st.session_state.get('audio_autoplay', True), key="audio_autoplay_toggle")
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
        if HAS_PERSONA_BOT:
            try:
                st.session_state.bot = PersonaBot(st.session_state.kb_id, model_id)
                st.success("✓ Connected!")
            except Exception as e:
                st.error(f"Error: {e}")

# Welcome message if no chat history
if not st.session_state.chat_history:
    st.markdown("""
    <div class="welcome-text">
        <h2>Welcome to Lecture Bot!</h2>
        <p>I'm Professor Levine's AI assistant. I can help you with:</p>
        <ul>
            <li>Course content and lecture materials</li>
            <li>UX design principles and methodologies</li>
            <li>Assignment guidance and clarification</li>
            <li>Portfolio examples and case studies</li>
        </ul>
    </div>
    """, unsafe_allow_html=True)

# Display chat history
for idx, chat in enumerate(st.session_state.chat_history):
    # User message
    st.markdown(f'<div class="user-message">{chat["question"]}</div>', unsafe_allow_html=True)
    
    # Bot message
    st.markdown(f'<div class="bot-message">{chat["answer"]}</div>', unsafe_allow_html=True)
    
    # Audio player (visible with controls, autoplay based on setting)
    if st.session_state.voice_enabled and chat.get('audio_base64'):
        st.audio(
            f"data:audio/mpeg;base64,{chat['audio_base64']}",
            format="audio/mpeg",
            autoplay=st.session_state.audio_autoplay
        )
    
    # Learning Cards (only for most recent message)
    if idx == len(st.session_state.chat_history) - 1 and chat.get('learning_cards'):
        render_learning_cards(chat['learning_cards'], idx)
    
    # Sources
    if chat.get('sources'):
        with st.expander("📎 Sources", expanded=False):
            for source in chat['sources']:
                st.caption(source)
    
    # Follow-up prompts (only for last message) - REMOVED, replaced by learning cards
    # if idx == len(st.session_state.chat_history) - 1 and not chat.get('safety_triggered'):
    #     st.markdown("##### 💡 Dive deeper:")
    #     col1, col2, col3 = st.columns(3)
    #     
    #     with col1:
    #         if st.button("🏢 Real-world example", key=f"example_{idx}", use_container_width=True):
    #             st.session_state.pending_question = f"Can you share a real-world example from your professional experience related to: {chat['question']}"
    #             st.rerun()
    #     
    #     with col2:
    #         if st.button("📖 Explain more", key=f"explain_{idx}", use_container_width=True):
    #             st.session_state.pending_question = f"Can you explain this concept in more detail: {chat['question']}"
    #             st.rerun()
    #     
    #     with col3:
    #         if st.button("🔗 How does this connect?", key=f"connect_{idx}", use_container_width=True):
    #             st.session_state.pending_question = f"How does this concept connect to other topics we've covered: {chat['question']}"
    #             st.rerun()

# Handle pending question from follow-up button
if st.session_state.pending_question:
    question = st.session_state.pending_question
    st.session_state.pending_question = None
    
    # User message
    st.markdown(f'<div class="user-message">{question}</div>', unsafe_allow_html=True)
    
    # Bot message placeholder
    bot_placeholder = st.empty()
    cards_placeholder = st.empty()
    
    with st.spinner("Professor Levine is thinking..."):
        try:
            # Apply verbosity
            verbosity_prompts = {
                "brief": "Provide a brief, concise response (2-3 sentences). Be direct and specific.",
                "normal": "Provide a clear, conversational response with relevant examples from the course materials.",
                "detailed": "Provide a comprehensive response with specific examples, methodologies, and references to course materials and portfolio work."
            }
            
            modified_question = f"{verbosity_prompts[st.session_state.verbosity]} {question}"
            
            # Query bot
            result = st.session_state.bot.query(modified_question, use_persona=True)
            result['question'] = question
            
            # Show response
            bot_placeholder.markdown(f'<div class="bot-message">{result["answer"]}</div>', unsafe_allow_html=True)
            
            # Generate audio if voice is enabled
            if st.session_state.voice_enabled and st.session_state.voice_generator:
                try:
                    audio_base64 = st.session_state.voice_generator.generate_audio_base64(
                        result['answer'], 
                        voice="chris"
                    )
                    result['audio_base64'] = audio_base64
                except Exception as e:
                    pass  # Silently fail
            
            st.session_state.chat_history.append(result)
        except Exception as e:
            st.error(f"Error: {e}")
    st.rerun()

# Chat input
# Add CSS to make footer transparent and add purple triangle
st.markdown("""
<style>
    /* Transparent footer - let purple background show through */
    section[data-testid="stBottom"] {
        background-color: transparent !important;
        background: transparent !important;
    }
    
    /* Floating text box with white border */
    [data-testid="stChatInput"] input {
        border: 2px solid white !important;
        background: rgba(40, 40, 40, 0.85) !important;
        backdrop-filter: blur(10px);
        padding-left: 50px !important;
    }
    
    /* Purple triangle to the left */
    [data-testid="stChatInput"]::before {
        content: "▶";
        position: absolute;
        left: 20px;
        top: 50%;
        transform: translateY(-50%);
        color: #7B2FFF;
        font-size: 20px;
        z-index: 10;
    }
</style>
""", unsafe_allow_html=True)

question = st.chat_input("Ask Professor Levine...")

if question and st.session_state.bot:
    # User message
    st.markdown(f'<div class="user-message">{question}</div>', unsafe_allow_html=True)
    
    # Placeholders for bot response and cards
    bot_placeholder = st.empty()
    cards_placeholder = st.empty()
    
    with st.spinner("Professor Levine is thinking..."):
        try:
            # Apply verbosity
            verbosity_prompts = {
                "brief": "Provide a brief, concise response (2-3 sentences). Be direct and specific.",
                "normal": "Provide a clear, conversational response with relevant examples from the course materials.",
                "detailed": "Provide a comprehensive response with specific examples, methodologies, and references to course materials and portfolio work."
            }
            
            modified_question = f"{verbosity_prompts[st.session_state.verbosity]} {question}"
            
            # Query bot
            result = st.session_state.bot.query(modified_question, use_persona=True)
            result['question'] = question
            
            # Show response
            bot_placeholder.markdown(f'<div class="bot-message">{result["answer"]}</div>', unsafe_allow_html=True)
            
            # Generate audio if voice is enabled
            if st.session_state.voice_enabled and st.session_state.voice_generator:
                try:
                    audio_base64 = st.session_state.voice_generator.generate_audio_base64(
                        result['answer'], 
                        voice="chris"
                    )
                    result['audio_base64'] = audio_base64
                except Exception as e:
                    pass  # Silently fail
            
            st.session_state.chat_history.append(result)
        except Exception as e:
            st.error(f"Error: {e}")
    st.rerun()
elif question and not st.session_state.bot:
    st.error("Please connect to the bot in the sidebar settings first!")
