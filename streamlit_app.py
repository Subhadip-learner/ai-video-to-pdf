# Import the streamlit library to build the web UI
import streamlit as st

# Standard library imports for file and time handling
import os           # for checking file existence and removing files
import tempfile     # for staging uploaded videos before processing
import time         # to create timestamps and measure durations

# Import the processor class from video_processor and alias it so your app uses "OptimizedVideoProcessor"
# We're importing SimpleVideoProcessor but keeping the name OptimizedVideoProcessor for compatibility.
from video_processor import SimpleVideoProcessor as OptimizedVideoProcessor

# -----------------------
# Page configuration
# -----------------------
# Configure the Streamlit app page metadata and layout
st.set_page_config(
    page_title="AI Video to PDF Converter",  # The browser tab title
    page_icon="📚",                           # The tab icon (emoji)
    layout="wide",                            # Use the full width of the window
    initial_sidebar_state="expanded"          # Start with the sidebar expanded
)

# -----------------------
# Custom CSS for styling
# -----------------------
# Inject CSS into the Streamlit page to style text, cards, boxes, etc.
# unsafe_allow_html=True is required so Streamlit accepts raw HTML/CSS.
st.markdown("""
<style>
    .main-header {
        font-size: 3rem;
        color: #1f77b4;
        text-align: center;
        margin-bottom: 2rem;
        font-weight: bold;
    }
    .feature-card {
        background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
        color: white;
        padding: 1.5rem;
        border-radius: 15px;
        margin: 1rem 0;
        box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
    }
    .success-box {
        background-color: #d4edda;
        color: #155724;
        padding: 1rem;
        border-radius: 10px;
        border: 1px solid #c3e6cb;
        margin: 1rem 0;
    }
    .error-box {
        background-color: #f8d7da;
        color: #721c24;
        padding: 1rem;
        border-radius: 10px;
        border: 1px solid #f5c6cb;
        margin: 1rem 0;
    }
    .info-box {
        background-color: #d1ecf1;
        color: #0c5460;
        padding: 1.5rem;
        border-radius: 10px;
        border: 1px solid #bee5eb;
        margin: 1rem 0;
    }
    .input-section {
        background-color: #f8f9fa;
        padding: 2rem;
        border-radius: 15px;
        border: 2px solid #e9ecef;
        margin: 2rem 0;
    }
    .input-header {
        color: #1f77b4;
        border-bottom: 2px solid #1f77b4;
        padding-bottom: 0.5rem;
        margin-bottom: 1.5rem;
    }
    .important-notes {
        background-color: #fff3cd;
        border: 1px solid #ffeaa7;
        border-radius: 10px;
        padding: 1.5rem;
        margin: 1rem 0;
        color: #856404 !important;
    }
    .important-notes p {
        color: #856404 !important;
        margin-bottom: 0.8rem;
        font-size: 0.9rem;
    }
    .important-notes strong {
        color: #856404 !important;
    }
    .processing-status {
        background-color: #f8f9fa;
        padding: 2rem;
        border-radius: 10px;
        border: 2px solid #e9ecef;
        margin: 2rem 0;
    }
    .status-item {
        display: flex;
        align-items: center;
        margin: 0.5rem 0;
        padding: 0.5rem;
        border-radius: 5px;
    }
    .status-checkbox {
        margin-right: 10px;
        font-size: 1.2rem;
    }
    .status-completed {
        color: #28a745;
        background-color: #f8fff9;
    }
    .status-pending {
        color: #6c757d;
        background-color: #f8f9fa;
    }
</style>
""", unsafe_allow_html=True)

# -----------------------
# Main application function
# -----------------------
def main():
    # Display the big header at the top using the CSS class defined above
    st.markdown('<h1 class="main-header">🧠 AI Video to PDF Converter</h1>', unsafe_allow_html=True)
    
    # Show an introductory information box describing the app
    st.markdown("""
    <div class="info-box">
        <h3 style='color: #1f77b4; margin-top: 0;'>🚀 Transform Educational Videos into Smart PDF Notes</h3>
        <p style='color: #333; font-size: 1.1rem; margin-bottom: 0;'>
        Our AI-powered system intelligently analyzes educational videos to extract key slides and content, 
        creating comprehensive PDF notes automatically.
        </p>
    </div>
    """, unsafe_allow_html=True)
    
    # Section heading for input area
    st.markdown("## 📥 Video Processing Input")
    
    # Create a container for the input form and UI
    with st.container():
        # open a styled block (we inject the opening div here and close it later)
        st.markdown('<div class="input-section">', unsafe_allow_html=True)
        
        # Use a form so submission can be controlled (prevents immediate re-run on each change)
        with st.form("video_processing_form"):
            # Create two columns inside the form for layout
            col1, col2 = st.columns(2)
            
            # Left column: video details inputs
            with col1:
                st.markdown("### 🎥 Video Details")
                # Text input for the YouTube URL (single-line)
                video_url = st.text_input(
                    "**YouTube Video URL**",
                    placeholder="https://www.youtube.com/watch?v=...",
                    help="Enter the full YouTube URL of the educational video you want to convert"
                )
                
                # Text input for naming the resulting content/PDF
                content_name = st.text_input(
                    "**Content Name**",
                    placeholder="e.g., Machine_Learning_Lecture_1",
                    help="This will be used as the filename for your PDF"
                )

                # Direct upload fallback for videos that can't be downloaded
                # (e.g. YouTube bot checks blocking the server's IP address).
                uploaded_video = st.file_uploader(
                    "**Or upload a video file**",
                    type=["mp4", "mkv", "webm", "avi", "mov", "m4v", "mpeg", "mpg"],
                    help="If the YouTube download fails, download the video yourself and upload it here instead"
                )
            
            # Right column: processing settings and optional training PDF
            with col2:
                st.markdown("### ⚙️ Processing Settings")
                # Quality selection for download (affects resolution requested from yt_dlp)
                quality = st.selectbox(
                    "**Video Quality**",
                    options=["1080p", "720p", "480p", "360p"],
                    index=1,
                    help="Higher quality = better results but longer processing time"
                )
                
                st.info(
                    "Frames are selected using visual similarity, sharpness, and optional OCR. "
                    "Reference-PDF training is not available in this version."
                )
            
            # Visual separator inside the form
            st.markdown("---")
            # The form submit button; action happens only when this is pressed
            submitted = st.form_submit_button(
                "🚀 Start Intelligent Processing",
                use_container_width=True,
                type="primary"
            )
        
        # Close the styled input-section div
        st.markdown('</div>', unsafe_allow_html=True)

    # Reserve a container for processing status updates (we will write into it when processing starts)
    processing_container = st.container()
    
    # Features section heading
    st.markdown("## ✨ Key Features")
    # Two-column layout to show feature cards
    col1, col2 = st.columns(2)
    
    # Left column feature cards
    with col1:
        st.markdown("""
        <div class="feature-card">
            <h3>🎯 Smart Frame Selection</h3>
            <p>Uses sharpness and visual similarity to retain useful frames</p>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("""
        <div class="feature-card">
            <h3>🔄 Smart Replacement</h3>
            <p>Replaces similar frames with better quality versions</p>
        </div>
        """, unsafe_allow_html=True)
    
    # Right column feature cards
    with col2:
        st.markdown("""
        <div class="feature-card">
            <h3>📚 Text-Aware Analysis</h3>
            <p>Detects educational content using text recognition</p>
        </div>
        """, unsafe_allow_html=True)
        st.markdown("""
        <div class="feature-card">
            <h3>🛟 Reliable Fallback</h3>
            <p>Uniform sampling helps ensure a PDF is produced for static videos</p>
        </div>
        """, unsafe_allow_html=True)

    # Sidebar with important notes (persistent on side)
    with st.sidebar:
        st.markdown("## ⚠️ Important Notes")
        st.markdown("""
        <div class="important-notes">
        <p><strong>Videos must be publicly accessible on YouTube</strong></p>
        <p><strong>Processing time varies with video length</strong></p>
        <p><strong>For best results, use videos with clear slides</strong></p>
        <p><strong>Large videos may take several minutes to process</strong></p>
        </div>
        """, unsafe_allow_html=True)

    # -----------------------
    # Processing logic triggered on form submit
    # -----------------------
    if submitted:
        # Validate user input: need either a URL or an uploaded file
        if not video_url and uploaded_video is None:
            st.error("❌ Please enter a YouTube URL or upload a video file.")
            return  # early return to stop the function
        
        # If user didn't provide a content name, create a timestamp-based fallback name
        if not content_name:
            content_name = f"smart_notes_{int(time.time())}"
        
        # Quick URL format check (not exhaustive) - warn but continue.
        # Skipped when the user uploaded a file instead of pasting a URL.
        if video_url and "youtube.com" not in video_url and "youtu.be" not in video_url:
            st.warning("⚠️ Please check the YouTube URL (must contain youtube.com or youtu.be)")
        
        # Wrap the heavy processing in try/except to show errors in UI instead of crashing
        try:
            with processing_container:
                # Show processing status header and a styled area
                st.markdown("## 🔄 Processing Status")
                st.markdown('<div class="processing-status">', unsafe_allow_html=True)
                
                # Define a list of steps to display progress
                steps = [
                    "Initializing AI Processor...",
                    "Downloading video...",
                    "Extracting distinct keyframes...",
                    "Filtering redundant frames...",
                    "Creating PDF document...",
                    "Finalizing and saving..."
                ]
                # Create a placeholder that we will update with HTML steps
                status_placeholder = st.empty()

                # Local helper function to update the step UI
                def update(step_idx, done=False):
                    """
                    step_idx: index of the current step being processed
                    done: if True, mark the current step as completed
                    This function builds small HTML fragments showing completed/pending steps.
                    """
                    html = ""
                    for i, step in enumerate(steps):
                        if i < step_idx:
                            # Already completed steps get a green check
                            html += f'<div class="status-item status-completed"><span class="status-checkbox">✅</span> {step}</div>'
                        elif i == step_idx and not done:
                            # Current step being processed shows an hourglass
                            html += f'<div class="status-item status-pending"><span class="status-checkbox">⏳</span> {step}</div>'
                        elif i == step_idx and done:
                            # Mark current step as completed
                            html += f'<div class="status-item status-completed"><span class="status-checkbox">✅</span> {step}</div>'
                        else:
                            # Future steps are shown as pending/empty
                            html += f'<div class="status-item status-pending"><span class="status-checkbox">⬜</span> {step}</div>'
                    # Write the composed HTML into the placeholder
                    status_placeholder.markdown(html, unsafe_allow_html=True)

                # Initialize processor: mark step 0 as started, sleep 1s to show change (cosmetic)
                update(0); time.sleep(1)
                processor = OptimizedVideoProcessor()  # instantiate the video processor

                # Run the full processing pipeline.
                # Uploaded files skip the YouTube download entirely.
                if uploaded_video is not None:
                    suffix = os.path.splitext(uploaded_video.name)[1] or ".mp4"
                    with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
                        tmp.write(uploaded_video.getbuffer())
                        staged_path = tmp.name
                    try:
                        pdf_output = processor.process_file_to_pdf(staged_path, content_name)
                    finally:
                        try:
                            os.remove(staged_path)
                        except OSError:
                            pass
                else:
                    pdf_output = processor.process_video_to_pdf(video_url, content_name, quality=quality)
                
                # After run, check if a PDF was created and exists on disk
                if pdf_output and os.path.exists(pdf_output):
                    # Mark final step completed
                    update(len(steps)-1, True)
                    st.success("🎉 Processing Completed Successfully!")
                    
                    # Show a short processing report using metrics and three columns
                    st.markdown("### 📊 Processing Report")
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        # Display number of extracted slides from processor.stats (compatibility alias)
                        st.metric("Extracted Slides", processor.stats['key_frames'])
                        st.metric("Total Frames", f"{processor.stats['total_frames']:,}")
                    with col2:
                        # Video duration: note the key in stats is 'video_duration'; the UI used 'duration' earlier.
                        # To avoid KeyError, we show video_duration if available; otherwise show a placeholder.
                        vid_dur = processor.stats.get('video_duration', None)
                        if vid_dur is None:
                            st.metric("Video Duration", "Unknown")
                        else:
                            st.metric("Video Duration", f"{vid_dur:.1f} sec")
                        st.metric("Processing Quality", "Optimized")
                    with col3:
                        st.metric("Status", "Completed")
                        st.metric("Output", "PDF Generated")
                    
                    # Provide a download button for the generated PDF
                    st.markdown("### 📥 Download Your PDF")
                    with open(pdf_output, "rb") as f:
                        pdf_data = f.read()
                    st.download_button(
                        label=f"📄 Download {os.path.basename(pdf_output)}",
                        data=pdf_data,
                        file_name=os.path.basename(pdf_output),
                        mime="application/pdf",
                        use_container_width=True
                    )
                    # Play balloons as a small celebration
                    st.balloons()
                else:
                    # Show a useful processor error when one is available.
                    st.error(processor.last_error or "❌ Failed to create PDF. Please try another video.")
        
        except Exception as e:
            # Catch-all errors are shown in the UI rather than raising an unhandled exception
            st.error(f"💥 Error: {str(e)}")

# Standard Python entrypoint: run main() when the script is executed directly
if __name__ == "__main__":
    main()
