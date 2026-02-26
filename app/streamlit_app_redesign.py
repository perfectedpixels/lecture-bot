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


def render_skeleton_loading():
    """Render skeleton loading animation while cards are being generated"""
    st.markdown("""
    <div class="learning-cards-container loading-cards">
        <div class="skeleton skeleton-title"></div>
        
        <div class="skeleton skeleton-card"></div>
        <div class="skeleton skeleton-text"></div>
        <div class="skeleton skeleton-text-short"></div>
        
        <div class="skeleton skeleton-card" style="margin-top: 20px;"></div>
        <div class="skeleton skeleton-text"></div>
        <div class="skeleton skeleton-text-short"></div>
        
        <div class="skeleton skeleton-card" style="margin-top: 20px;"></div>
        <div class="skeleton skeleton-text"></div>
        <div class="skeleton skeleton-text-short"></div>
    </div>
    """, unsafe_allow_html=True)


def render_learning_cards(cards: dict, message_idx: int):
    """Render all three types of learning cards in a compact side-by-side layout"""
    if not cards or not any(cards.values()):
        return
    
    st.markdown("""
    <div class="learning-cards-title">
        💡 Explore Related Topics
    </div>
    """, unsafe_allow_html=True)
    
    # Create two columns for side-by-side cards
    col1, col2 = st.columns(2)
    
    with col1:
        # Core Teaching Concepts Card
        if cards.get('teaching_concepts'):
            render_teaching_concepts_card(cards['teaching_concepts'], message_idx)
    
    with col2:
        # See It in Practice Card
        if cards.get('portfolio_examples'):
            render_portfolio_card(cards['portfolio_examples'], message_idx)


def render_teaching_concepts_card(concepts: list, message_idx: int):
    """Render the teaching concepts card with clickable topics"""
    if not concepts:
        return
    
    st.markdown("""
    <div class="card-section">
        <div class="card-section-title">📚 Core Teaching Concepts</div>
    """, unsafe_allow_html=True)
    
    for i, concept in enumerate(concepts[:3]):
        concept_key = f"teaching_{message_idx}_{i}"
        
        # Initialize expansion state
        if concept_key not in st.session_state:
            st.session_state[concept_key] = False
        
        # Clickable concept button
        if st.button(
            f"📖 {concept['concept']}", 
            key=f"concept_btn_{concept_key}",
            use_container_width=True,
            help=concept['relevance']
        ):
            st.session_state[concept_key] = not st.session_state[concept_key]
        
        # Show expanded content
        if st.session_state[concept_key]:
            st.markdown(f"""
            <div class="expanded-content">
                <strong>Definition:</strong> {concept.get('definition', 'N/A')}<br><br>
                <strong>Key Principles:</strong>
                <ul>
                    {''.join([f'<li>{p}</li>' for p in concept.get('key_principles', [])[:3]])}
                </ul>
            </div>
            """, unsafe_allow_html=True)
    
    st.markdown("</div>", unsafe_allow_html=True)



def render_portfolio_card(projects: list, message_idx: int):
    """Render the portfolio examples card with summaries and lecture context"""
    if not projects:
        return
    
    st.markdown("""
    <div class="card-section">
        <div class="card-section-title">🎨 See It in Practice</div>
    """, unsafe_allow_html=True)
    
    for i, project in enumerate(projects[:3]):
        project_key = f"portfolio_{message_idx}_{i}"
        
        # Initialize expansion state
        if project_key not in st.session_state:
            st.session_state[project_key] = False
        
        # Generate 10-word summary
        project_name = project['title'].replace('-', ' ').title()
        reasons = project.get('reasons', [])
        summary = ' '.join(reasons[0].split()[:10]) if reasons else "Real-world application example"
        
        # Clickable project button with summary
        if st.button(
            f"🏢 {project_name}",
            key=f"project_btn_{project_key}",
            use_container_width=True,
            help=summary
        ):
            st.session_state[project_key] = not st.session_state[project_key]
        
        # Display lecture context if expanded
        if st.session_state[project_key]:
            st.markdown(f"""
            <div class="expanded-content">
                <strong>Summary:</strong> {summary}<br><br>
                <strong>Relevant to:</strong>
                <ul>
                    {''.join([f'<li>{reason}</li>' for reason in reasons[:3]])}
                </ul>
                <em>This example was discussed in lecture to demonstrate these concepts in practice.</em>
            </div>
            """, unsafe_allow_html=True)
    
    st.markdown("</div>", unsafe_allow_html=True)


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
        background: rgba(255, 255, 255, 0.15);
        border: 1px solid rgba(255, 255, 255, 0.3);
        color: white !important;
        border-radius: 8px;
        padding: 8px 16px;
        transition: all 0.2s;
    }
    
    .stButton button:hover {
        background: rgba(255, 255, 255, 0.25);
        border-color: rgba(255, 255, 255, 0.5);
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
    
    /* Learning Cards Styling */
    .learning-cards-title {
        font-size: 20px;
        font-weight: bold;
        color: white;
        margin: 20px 0 15px 0;
        text-align: center;
    }
    
    .card-section {
        background: rgba(255, 255, 255, 0.20);
        border: 1px solid rgba(255, 255, 255, 0.35);
        border-radius: 12px;
        padding: 20px;
        margin-bottom: 15px;
        backdrop-filter: blur(15px);
        box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
    }
    
    .card-section-title {
        font-size: 16px;
        font-weight: bold;
        color: white;
        margin-bottom: 15px;
        padding-bottom: 10px;
        border-bottom: 1px solid rgba(255, 255, 255, 0.2);
    }
    
    .expanded-content {
        background: rgba(0, 0, 0, 0.25);
        padding: 15px;
        border-radius: 8px;
        margin: 10px 0;
        color: white;
        font-size: 14px;
        line-height: 1.6;
    }
    
    .expanded-content ul {
        margin: 10px 0;
        padding-left: 20px;
    }
    
    .expanded-content li {
        margin: 5px 0;
    }
    
    /* Skeleton Loading Animation */
    .skeleton {
        background: linear-gradient(
            90deg,
            rgba(255, 255, 255, 0.08) 25%,
            rgba(255, 255, 255, 0.15) 50%,
            rgba(255, 255, 255, 0.08) 75%
        );
        background-size: 200% 100%;
        animation: shimmer 1.5s infinite;
        border-radius: 6px;
    }
    
    @keyframes shimmer {
        0% {
            background-position: 200% 0;
        }
        100% {
            background-position: -200% 0;
        }
    }
    
    .skeleton-title {
        height: 24px;
        width: 60%;
        margin-bottom: 15px;
    }
    
    .skeleton-card {
        height: 80px;
        margin: 10px 0;
    }
    
    .skeleton-text {
        height: 16px;
        width: 100%;
        margin: 8px 0;
    }
    
    .skeleton-text-short {
        height: 16px;
        width: 70%;
        margin: 8px 0;
    }
    
    .loading-cards {
        padding: 20px;
    }
    
    .learning-cards-title {
        font-size: 18px;
        font-weight: 600;
        margin-bottom: 15px;
        color: white;
        display: flex;
        align-items: center;
        gap: 8px;
    }
    
    .card-section {
        margin: 15px 0;
        padding: 15px;
        background: rgba(255, 255, 255, 0.05);
        border-radius: 10px;
        border: 1px solid rgba(255, 255, 255, 0.15);
    }
    
    .card-section-title {
        font-size: 16px;
        font-weight: 600;
        margin-bottom: 12px;
        color: #E0B0FF;
    }
    
    .concept-item {
        padding: 10px 12px;
        margin: 8px 0;
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
    
    # Audio player (visible with controls so user can stop it)
    if st.session_state.voice_enabled and chat.get('audio_base64'):
        st.audio(
            f"data:audio/mpeg;base64,{chat['audio_base64']}",
            format="audio/mpeg",
            autoplay=True
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
            
            # Show skeleton loading for cards
            with cards_placeholder:
                render_skeleton_loading()
            
            result = st.session_state.bot.query(modified_question, use_persona=True)
            result['question'] = question
            
            # Clear skeleton and show actual response
            bot_placeholder.markdown(f'<div class="bot-message">{result["answer"]}</div>', unsafe_allow_html=True)
            cards_placeholder.empty()
            
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
            
            # Show skeleton loading for cards
            with cards_placeholder:
                render_skeleton_loading()
            
            result = st.session_state.bot.query(modified_question, use_persona=True)
            result['question'] = question
            
            # Clear skeleton and show actual response
            bot_placeholder.markdown(f'<div class="bot-message">{result["answer"]}</div>', unsafe_allow_html=True)
            cards_placeholder.empty()
            
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
