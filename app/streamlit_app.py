import streamlit as st
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..', 'src'))

from persona_bot_safe import PersonaBot
from preprocessing.transcript_cleaner import TranscriptCleaner
from preprocessing.concept_extractor import ConceptExtractor
from preprocessing.affinity_mapper import AffinityMapper
from preprocessing.pipeline import LecturePreprocessingPipeline as PreprocessingPipeline
import json
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from pathlib import Path

st.set_page_config(
    page_title="Lecture Bot",
    page_icon="🎓",
    layout="wide"
)

# Initialize session state
if 'chat_history' not in st.session_state:
    st.session_state.chat_history = []
if 'persona_history' not in st.session_state:
    st.session_state.persona_history = []
if 'bot' not in st.session_state:
    st.session_state.bot = None
if 'processed_transcripts' not in st.session_state:
    st.session_state.processed_transcripts = []
if 'concept_map' not in st.session_state:
    st.session_state.concept_map = None
if 'persona_mode' not in st.session_state:
    st.session_state.persona_mode = True
if 'affinity_map' not in st.session_state:
    st.session_state.affinity_map = None

# Sidebar configuration
with st.sidebar:
    st.title("Settings")

    # Persona settings
    st.markdown("### Persona Settings")

    persona_mode = st.checkbox(
        "Enable Persona Mode",
        value=st.session_state.persona_mode,
        help="Bot responds as the instructor"
    )
    st.session_state.persona_mode = persona_mode

    # Affinity map upload
    affinity_file = st.file_uploader(
        "Affinity Map (optional)",
        type=['json'],
        help="Upload affinity_map.json from preprocessing"
    )

    if affinity_file:
        affinity_path = Path("temp_affinity_map.json")
        affinity_path.write_bytes(affinity_file.read())
        st.session_state.affinity_map = str(affinity_path)
        st.success("Affinity map loaded")

    if st.button("Connect", type="primary"):
        try:
            st.session_state.bot = PersonaBot(
                affinity_map_path=st.session_state.get('affinity_map'),
            )
            st.success("Connected!")
        except Exception as e:
            st.error(f"Error: {e}")

    st.divider()

    st.markdown("### Features")
    st.markdown("""
    - Persona-based responses
    - Concept-aware context
    - Source attribution
    - Affinity mapping
    - Assignment feedback
    """)

# Main content
st.title("🎓 Lecture Bot")
st.markdown("Ask questions, generate reports, and analyze your lecture content")

# Tabs for different features
tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs([
    "🎓 Persona Chat", 
    "🔧 Preprocess", 
    "🗺️ Concept Map",
    "💬 Q&A", 
    "📄 Reports", 
    "📊 Analysis"
])

with tab1:
    st.subheader("Ask Questions")
    
    if not st.session_state.bot:
        st.info("Please connect to the bot in the sidebar")
    else:
        # Display chat history
        for chat in st.session_state.chat_history:
            with st.chat_message("user"):
                st.write(chat['question'])
            with st.chat_message("assistant"):
                st.write(chat['answer'])
                if chat.get('sources'):
                    with st.expander("Sources"):
                        for source in chat['sources']:
                            st.text(source)

        # Chat input
        question = st.chat_input("Ask a question about your lectures...")

        if question:
            with st.chat_message("user"):
                st.write(question)

            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    result = st.session_state.bot.query(
                        question,
                        use_persona=st.session_state.persona_mode
                    )
                    st.write(result['answer'])

                    if result.get('relevant_concepts'):
                        with st.expander("Relevant Concepts"):
                            st.write(", ".join(result['relevant_concepts'][:10]))

                    with st.expander("Sources"):
                        for source in result['sources']:
                            st.text(source)

                    st.session_state.chat_history.append(result)

with tab2:
    st.subheader("🔧 Preprocess Transcripts")
    st.markdown("Clean, chunk, and tag your lecture transcripts")
    
    # File upload
    uploaded_file = st.file_uploader("Upload Raw Transcript", type=['txt'], help="Upload a raw lecture transcript with timestamps")
    
    if uploaded_file:
        raw_content = uploaded_file.read().decode('utf-8')
        
        col1, col2 = st.columns(2)
        
        with col1:
            st.markdown("#### Raw Transcript Preview")
            st.text_area("Raw", raw_content[:500] + "...", height=200, disabled=True)
        
        # Configuration
        st.markdown("#### Processing Options")
        speaker_name = st.text_input("Speaker name to remove", value="Jason Levine", help="e.g., 'Jason Levine:' will be removed")
        remove_timestamps = st.checkbox("Remove timestamps", value=True)
        extract_concepts = st.checkbox("Extract and tag concepts", value=True)
        
        if st.button("Process Transcript", type="primary"):
            with st.spinner("Processing..."):
                # Initialize pipeline
                pipeline = PreprocessingPipeline()
                
                # Clean transcript
                cleaner = TranscriptCleaner()
                cleaned = cleaner.clean(raw_content, speaker_name, remove_timestamps)
                
                # Extract concepts if requested
                concepts = []
                if extract_concepts:
                    extractor = ConceptExtractor()
                    concepts = extractor.extract_concepts(cleaned)
                
                # Chunk the content
                chunks = pipeline.chunk_text(cleaned)
                
                # Display results
                with col2:
                    st.markdown("#### Processed Transcript")
                    st.text_area("Cleaned", cleaned[:500] + "...", height=200, disabled=True)
                
                st.success(f"✓ Processed into {len(chunks)} chunks")
                
                if concepts:
                    st.markdown("#### 🏷️ Extracted Concepts")
                    concept_df = pd.DataFrame(concepts)
                    st.dataframe(concept_df, use_container_width=True)
                
                # Download options
                col_a, col_b, col_c = st.columns(3)
                
                with col_a:
                    st.download_button(
                        "Download Cleaned Text",
                        cleaned,
                        file_name=f"cleaned_{uploaded_file.name}",
                        mime="text/plain"
                    )
                
                with col_b:
                    if concepts:
                        st.download_button(
                            "Download Concepts (JSON)",
                            json.dumps(concepts, indent=2),
                            file_name=f"concepts_{uploaded_file.name}.json",
                            mime="application/json"
                        )
                
                with col_c:
                    chunks_json = json.dumps(chunks, indent=2)
                    st.download_button(
                        "Download Chunks (JSON)",
                        chunks_json,
                        file_name=f"chunks_{uploaded_file.name}.json",
                        mime="application/json"
                    )
                
                # Store in session state
                st.session_state.processed_transcripts.append({
                    'filename': uploaded_file.name,
                    'cleaned': cleaned,
                    'concepts': concepts,
                    'chunks': chunks
                })
    
    # Show previously processed transcripts
    if st.session_state.processed_transcripts:
        st.divider()
        st.markdown("#### Previously Processed")
        for idx, transcript in enumerate(st.session_state.processed_transcripts):
            with st.expander(f"📄 {transcript['filename']}"):
                st.write(f"Chunks: {len(transcript['chunks'])}")
                st.write(f"Concepts: {len(transcript['concepts'])}")
                if st.button(f"Index for search", key=f"upload_{idx}"):
                    st.info("Use scripts/ingest_to_chromadb.py to index processed transcripts")

with tab3:
    st.subheader("🗺️ Concept Affinity Map")
    st.markdown("Visualize concept clusters and relationships across all lectures")
    
    if not st.session_state.bot:
        st.info("Please connect to the bot in the sidebar")
    else:
        if st.button("Generate Affinity Map", type="primary"):
            with st.spinner("Analyzing concepts across all lectures..."):
                # This would ideally pull from your processed transcripts
                # For now, we'll query the KB for concept extraction
                mapper = AffinityMapper()
                
                # Simulate concept extraction from KB
                st.info("Note: For full functionality, process transcripts in the Preprocess tab first")
                
                # Create a sample visualization
                sample_concepts = [
                    {"concept": "AI", "count": 45, "category": "Technology"},
                    {"concept": "Design Thinking", "count": 38, "category": "Design"},
                    {"concept": "User Research", "count": 32, "category": "Design"},
                    {"concept": "Machine Learning", "count": 28, "category": "Technology"},
                    {"concept": "Prototyping", "count": 25, "category": "Design"},
                    {"concept": "Neural Networks", "count": 22, "category": "Technology"},
                    {"concept": "Biography", "count": 15, "category": "Personal"},
                    {"concept": "Frameworks", "count": 20, "category": "Methodology"},
                ]
                
                # Create network graph
                fig = go.Figure()
                
                # Add nodes
                for concept in sample_concepts:
                    fig.add_trace(go.Scatter(
                        x=[concept['count']],
                        y=[sample_concepts.index(concept)],
                        mode='markers+text',
                        marker=dict(size=concept['count'], color=concept['count'], colorscale='Viridis'),
                        text=concept['concept'],
                        textposition="middle right",
                        name=concept['category']
                    ))
                
                fig.update_layout(
                    title="Concept Frequency Map",
                    xaxis_title="Frequency",
                    yaxis_title="",
                    showlegend=True,
                    height=500
                )
                
                st.plotly_chart(fig, use_container_width=True)
                
                # Show concept table
                st.markdown("#### Concept Details")
                df = pd.DataFrame(sample_concepts)
                st.dataframe(df, use_container_width=True)

with tab4:
    st.subheader("💬 Q&A Mode")
    st.markdown("*Standard question-answering with source attribution*")
    
    if not st.session_state.bot:
        st.info("Please connect to the bot in the sidebar")
    else:
        # Display chat history
        for chat in st.session_state.chat_history:
            with st.chat_message("user"):
                st.write(chat['question'])
            with st.chat_message("assistant"):
                st.write(chat['answer'])
                if chat.get('sources'):
                    with st.expander("Sources"):
                        for source in chat['sources']:
                            st.text(source)

        # Chat input
        question = st.chat_input("Ask a question about your lectures...")

        if question:
            with st.chat_message("user"):
                st.write(question)

            with st.chat_message("assistant"):
                with st.spinner("Thinking..."):
                    result = st.session_state.bot.query(question)
                    st.write(result['answer'])

                    with st.expander("Sources"):
                        for source in result['sources']:
                            st.text(source)

                    st.session_state.chat_history.append(result)

with tab5:
    st.subheader("Generate Reports")
    
    if not st.session_state.bot:
        st.info("Please connect to the bot in the sidebar")
    else:
        col1, col2 = st.columns([3, 1])
        
        with col1:
            topic = st.text_input("Report Topic", placeholder="e.g., Machine Learning Fundamentals")
        
        with col2:
            st.write("")
            st.write("")
            generate = st.button("Generate Report", type="primary")
        
        if generate and topic:
            with st.spinner(f"Generating report on '{topic}'..."):
                report = st.session_state.bot.generate_report(topic)
                
                st.markdown("### Report")
                st.markdown(report)
                
                # Download button
                st.download_button(
                    label="Download Report",
                    data=report,
                    file_name=f"report_{topic.replace(' ', '_')}.txt",
                    mime="text/plain"
                )

with tab6:
    st.subheader("Content Analysis")
    
    if not st.session_state.bot:
        st.info("Please connect to the bot in the sidebar")
    else:
        analysis_type = st.selectbox(
            "Analysis Type",
            ["Concept Map", "Topic Summary", "Assignment Improvement", "Key Takeaways"]
        )
        
        if analysis_type == "Concept Map":
            concept = st.text_input("Enter concept to visualize", placeholder="e.g., Neural Networks")
            
            if st.button("Analyze") and concept:
                with st.spinner("Analyzing..."):
                    result = st.session_state.bot.query(
                        f"List all key concepts, subtopics, and relationships related to '{concept}' from the lectures. Format as a hierarchical structure."
                    )
                    
                    st.markdown("### Concept Analysis")
                    st.markdown(result['answer'])
                    
        elif analysis_type == "Topic Summary":
            topic = st.text_input("Topic to summarize", placeholder="e.g., Supervised Learning")
            
            if st.button("Summarize") and topic:
                with st.spinner("Summarizing..."):
                    result = st.session_state.bot.query(
                        f"Provide a concise summary of '{topic}' covering: definition, key points, examples, and applications mentioned in lectures."
                    )
                    
                    st.markdown("### Summary")
                    st.markdown(result['answer'])
                    
        elif analysis_type == "Assignment Improvement":
            st.markdown("Upload or paste your assignment for analysis")
            assignment = st.text_area("Assignment Content", height=200)
            
            if st.button("Analyze Assignment") and assignment:
                with st.spinner("Analyzing assignment..."):
                    result = st.session_state.bot.analyze_assignment(assignment)
                    
                    st.markdown("### Analysis & Suggestions")
                    st.markdown(result['answer'])
                    
                    if result.get('relevant_concepts'):
                        st.markdown("### 📚 Concepts to Review")
                        st.write(", ".join(result['relevant_concepts'][:8]))
                    
        else:  # Key Takeaways
            lecture_ref = st.text_input("Lecture reference or topic", placeholder="e.g., Week 3 or Introduction to AI")
            
            if st.button("Extract Takeaways") and lecture_ref:
                with st.spinner("Extracting key takeaways..."):
                    result = st.session_state.bot.query(
                        f"Extract the key takeaways and most important points from lectures about '{lecture_ref}'. Format as bullet points."
                    )
                    
                    st.markdown("### Key Takeaways")
                    st.markdown(result['answer'])



# Footer
st.divider()
st.markdown("""
<div style='text-align: center; color: gray;'>
    Built with Streamlit • Powered by Claude
</div>
""", unsafe_allow_html=True)
