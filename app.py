import os
import tempfile
import streamlit as st
from pipeline import (
    extract_from_pdf,
    extract_from_pptx,
    run_agentic_summarizer,
    build_narrated_video,
)

st.set_page_config(
    page_title="Synthetix AI Studio",
    page_icon="✨",
    layout="wide"
)

# High-End Custom Dashboard Styling
st.markdown("""
    <style>
    .stApp { background: #070b19; color: #f1f5f9; }
    .hero-card {
        background: linear-gradient(135deg, rgba(30, 41, 59, 0.7) 0%, rgba(15, 23, 42, 0.9) 100%);
        border: 1px solid rgba(99, 102, 241, 0.3);
        border-radius: 16px;
        padding: 2rem;
        box-shadow: 0 10px 30px rgba(0,0,0,0.5);
        margin-bottom: 2rem;
    }
    .stButton>button {
        background: linear-gradient(90deg, #6366f1 0%, #a855f7 100%);
        color: white;
        border: none;
        border-radius: 10px;
        padding: 0.6rem 1.4rem;
        font-weight: 600;
        width: 100%;
        box-shadow: 0 4px 15px rgba(99, 102, 241,.4);
    }
    .stButton>button:hover {
        transform: translateY(-2px);
        box-shadow: 0 6px 20px rgba(168, 85, 247, .6);
    }
    </style>
""", unsafe_allow_html=True)

with st.container():
    st.markdown("""
        <div class="hero-card">
            <h1>🎓 Synthetix AI: Lecture Slide-to-Video Studio</h1>
            <p style="color: #94a3b8; font-size: 1.1rem;">Transform bulky presentation decks into professional, studio-narrated revision videos using multi-agent AI and neural synthesis.</p>
        </div>
    """, unsafe_allow_html=True)

with st.sidebar:
    st.header("⚙️ Studio Settings")
    api_key = st.text_input("Gemini API Key", type="password", help="Paste your key from Google AI Studio")
    
    st.markdown("---")
    voice_choice = st.selectbox(
        "🎙️ Narrator Persona",
        [
            "en-US-AriaNeural (US Professional Female)",
            "en-US-GuyNeural (US Professional Male)",
            "en-IN-NeerjaNeural (Indian Academic Female)",
            "en-IN-PrabhatNeural (Indian Academic Male)"
        ]
    )
    voice_code = voice_choice.split(" ")[0]

    max_slides = st.slider("🎞️ Max Slides to Process", 3, 20, 6)
    st.markdown("---")
    st.info("💡 **Tip:** Export `.pptx` as `.pdf` to preserve vector diagrams and rich graphics!")

uploaded_file = st.file_uploader("📂 Upload Lecture Deck (.pdf or .pptx)", type=["pdf", "pptx"])

if uploaded_file and st.button("🚀 Synthesize HD Video Summary", type="primary"):
    if not api_key:
        st.error("⚠️ Please enter your Gemini API Key in the sidebar first.")
        st.stop()

    output_dir = tempfile.mkdtemp(prefix="lecture_video_")
    ext = uploaded_file.name.split(".")[-1].lower()
    input_path = os.path.join(output_dir, f"input_deck.{ext}")
    
    with open(input_path, "wb") as f:
        f.write(uploaded_file.read())

    progress_bar = st.progress(0)
    status_text = st.empty()

    with st.status("🎬 Processing Agentic Pipeline...", expanded=True) as status:
        status_text.text("1/3 Extracting frames & text layouts...")
        progress_bar.progress(20)
        
        is_pptx = (ext == "pptx")
        slides_data = extract_from_pptx(input_path, output_dir) if is_pptx else extract_from_pdf(input_path, output_dir)
        slides_data = slides_data[:max_slides]
        
        status_text.text("2/3 AI Agents generating executive summaries & scripts...")
        progress_bar.progress(50)
        lecture_script = run_agentic_summarizer(slides_data, api_key)
        
        status_text.text("3/3 Rendering neural TTS audio & high-speed MP4 video...")
        progress_bar.progress(85)
        video_path = build_narrated_video(
            slides_data=slides_data,
            lecture_script=lecture_script,
            is_pptx=is_pptx,
            voice=voice_code,
            output_dir=output_dir
        )
        progress_bar.progress(100)
        status.update(label="🎉 Video Synthesis Successful!", state="complete")

    st.markdown("---")
    col1, col2 = st.columns([3, 2], gap="large")

    with col1:
        st.subheader("🎥 Generated Video Player")
        st.video(video_path)
        with open(video_path, "rb") as vf:
            st.download_button(
                "⬇️ Download HD MP4 Video",
                data=vf,
                file_name="lecture_video_summary.mp4",
                mime="video/mp4"
            )

    with col2:
        st.subheader("📝 Executive Summary & Script")
        st.info(lecture_script.overall_summary)
        for s in lecture_script.slides:
            with st.expander(f"Slide {s.slide_number}: {s.title}"):
                st.markdown("**Key Takeaways:**")
                for kp in s.key_points:
                    st.markdown(f"- {kp}")
                st.markdown(f"**Narration Script:** *{s.narration_script}*")