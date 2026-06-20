import os
import tempfile
import numpy as np
import streamlit as st
from faster_whisper import WhisperModel
# MoviePy v2.0+ import paths
from moviepy.video.io.VideoFileClip import VideoFileClip
from moviepy.audio.AudioClip import AudioArrayClip

# Set up page styling
st.set_page_config(page_title="Interactive Video Censor", page_icon="🎬", layout="wide")

# --- CORE PROCESSING FUNCTIONS ---

def generate_bleep_wave(duration, fps=44100, frequency=1000):
    """Generates a 1kHz standard bleep tone (sine wave)."""
    num_samples = int(duration * fps)
    t = np.linspace(0, duration, num_samples, endpoint=False)
    wave = np.sin(2 * np.pi * frequency * t)
    stereo_wave = np.vstack((wave, wave)).T
    return stereo_wave

@st.cache_resource
def load_whisper_model():
    """Cache the model in memory so it doesn't reload on every action."""
    return WhisperModel("base", device="cpu", compute_type="int8")

def analyze_speech(input_path, bad_words_list):
    """Runs Whisper to get word timestamps and returns the initial word breakdown."""
    model = load_whisper_model()
    segments, info = model.transcribe(input_path, word_timestamps=True)
    
    words_timeline = []
    word_id = 0
    
    for segment in segments:
        for word_info in segment.words:
            word_text = word_info.word
            word_clean = word_text.strip().lower().strip(".,!?\"'")
            
            # Check if it should be auto-censored
            is_bad = word_clean in bad_words_list
            
            words_timeline.append({
                "id": word_id,
                "word": word_text,
                "start": word_info.start,
                "end": word_info.end,
                "censored": is_bad
            })
            word_id += 1
            
    return words_timeline

def render_censored_video(input_path, output_path, words_timeline):
    """Applies bleeps to the video based on the final curated words_timeline state."""
    video = VideoFileClip(input_path)
    fps = video.audio.fps
    audio_array = video.audio.to_soundarray()
    
    bleep_count = 0
    
    for item in words_timeline:
        if item["censored"]:
            bleep_count += 1
            start_sample = int(item["start"] * fps)
            end_sample = int(item["end"] * fps)
            
            target_length = end_sample - start_sample
            if target_length > 0:
                duration = target_length / fps
                bleep_wave = generate_bleep_wave(duration, fps=fps)
                
                # Math fix alignment mapping
                if bleep_wave.shape[0] < target_length:
                    padding = np.zeros((target_length - bleep_wave.shape[0], 2))
                    bleep_wave = np.vstack((bleep_wave, padding))
                elif bleep_wave.shape[0] > target_length:
                    bleep_wave = bleep_wave[:target_length, :]
                
                audio_array[start_sample:end_sample] = bleep_wave

    # Render final output file
    if bleep_count > 0:
        new_audio = AudioArrayClip(audio_array, fps=fps)
        final_video = video.with_audio(new_audio)
        final_video.write_videofile(output_path, codec="libx264", audio_codec="aac", logger=None)
    else:
        video.write_videofile(output_path, codec="libx264", audio_codec="aac", logger=None)
        
    video.close()
    return bleep_count

# --- STREAMLIT UI ---

st.title("🎬 Interactive Paragraph Auto-Censor")
st.markdown("Upload a video to auto-bleep words. Read the generated paragraph below to manually toggle any extra words.")

# Initialize complex session state architectures
if 'words_timeline' not in st.session_state:
    st.session_state['words_timeline'] = None
if 'temp_video_path' not in st.session_state:
    st.session_state['temp_video_path'] = None
if 'rendering_complete' not in st.session_state:
    st.session_state['rendering_complete'] = False
if 'final_output_bytes' not in st.session_state:
    st.session_state['final_output_bytes'] = None

# Sidebar Configurations
st.sidebar.header("🔧 Initial Auto-Censor Settings")
raw_bad_words = st.sidebar.text_area(
    "Automatic Banned Words (Comma Separated):", 
    value="swearword1, badword2, censor"
)
banned_words = [w.strip().lower() for w in raw_bad_words.split(",") if w.strip()]

uploaded_file = st.file_uploader("Choose an MP4 Video File", type=["mp4"])

if uploaded_file is not None:
    # Handle original path staging
    if st.session_state['temp_video_path'] is None:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as temp_in:
            temp_in.write(uploaded_file.read())
            st.session_state['temp_video_path'] = temp_in.name
            st.session_state['words_timeline'] = None # Reset on new file load

    col1, col2 = st.columns([1, 1])
    
    with col1:
        st.subheader("Original Video")
        st.video(uploaded_file)

    with col2:
        st.subheader("1. Run Initial AI Scan")
        if st.button("🚀 Analyze Audio & Flag Words", use_container_width=True):
            with st.spinner("Whisper AI is creating transcription mapping timeline..."):
                st.session_state['words_timeline'] = analyze_speech(st.session_state['temp_video_path'], banned_words)
                st.session_state['rendering_complete'] = False # Reset render tracking flag

# --- INTERACTIVE TRANSCRIPT PARAGRAPH ---
if st.session_state['words_timeline'] is not None:
    st.write("---")
    st.subheader("📝 Interactive Review Paragraph")
    st.markdown("Read the text below. Words highlighted in **Red** are scheduled for bleeps. **Click any word** to toggle its censorship status manually.")
    
    # We use Streamlit container columns to render words inline like a paragraph block safely
    word_container = st.container()
    
    with word_container:
        # Create visual presentation rows
        cols = st.columns(12)  # Display up to 12 words per structural line row block
        for index, item in enumerate(st.session_state['words_timeline']):
            col_idx = index % 12
            with cols[col_idx]:
                # Style active targets versus regular transcript pieces
                btn_type = "secondary"
                label_display = item["word"]
                
                if item["censored"]:
                    label_display = f"🤬 {label_display.strip()}"
                    # Use unique styling indicator via key manipulation or label markers
                
                # Assign unique button states 
                if st.button(label_display, key=f"word_btn_{item['id']}", use_container_width=True):
                    # Toggle mapping state logic direct on target indices
                    st.session_state['words_timeline'][index]['censored'] = not item['censored']
                    st.session_state['rendering_complete'] = False # State changed, requires fresh render
                    st.rerun()

    st.write("---")
    st.subheader("2. Finalize Video Track Output")
    
    if st.button("🛠️ Apply Review & Build Censored Video", type="primary", use_container_width=True):
        with st.spinner("Processing final video matrix edits..."):
            temp_out_path = os.path.join(tempfile.gettempdir(), "final_interactive_output.mp4")
            
            bleeps_applied = render_censored_video(
                st.session_state['temp_video_path'], 
                temp_out_path, 
                st.session_state['words_timeline']
            )
            
            with open(temp_out_path, "rb") as f:
                st.session_state['final_output_bytes'] = f.read()
                
            st.session_state['rendering_complete'] = True
            st.session_state['total_applied_bleeps'] = bleeps_applied
            os.remove(temp_out_path)

    # Offer download button only when build actions complete cleanly
    if st.session_state['rendering_complete']:
        st.success(f"Successfully processed! Final version contains {st.session_state['total_applied_bleeps']} bleeped audio sequences.")
        st.download_button(
            label="📥 Download Censored Video MP4",
            data=st.session_state['final_output_bytes'],
            file_name="interactive_censored_video.mp4",
            mime="video/mp4",
            use_container_width=True
        )
