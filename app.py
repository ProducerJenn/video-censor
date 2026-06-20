import os
import tempfile
import numpy as np
import streamlit as st
from faster_whisper import WhisperModel
from moviepy.video.io.VideoFileClip import VideoFileClip
from moviepy.audio.AudioClip import AudioArrayClip
# Set up page styling
st.set_page_config(page_title="Auto Video Censor", page_icon="🎬", layout="wide")

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
    """Cache the model in memory so it doesn't reload on every button click."""
    return WhisperModel("base", device="cpu", compute_type="int8")

def process_video(input_path, output_path, bad_words_list):
    """Transcribes the video, updates the audio array, and saves the censored video."""
    video = VideoFileClip(input_path)
    fps = video.audio.fps
    audio_array = video.audio.to_soundarray()
    
    model = load_whisper_model()
    # word_timestamps=True tracks exact positioning of syllables
    segments, info = model.transcribe(input_path, word_timestamps=True)
    
    bleep_count = 0
    full_transcript_data = []

    # Read layout segments
    for segment in segments:
        for word_info in segment.words:
            word_clean = word_info.word.strip().lower().strip(".,!?\"'")
            start_time = word_info.start
            end_time = word_info.end
            
            # Record text for the review transcript component
            is_bad = word_clean in bad_words_list
            full_transcript_data.append({
                "word": word_info.word, 
                "start": start_time, 
                "end": end_time, 
                "censored": is_bad
            })
            
            if is_bad:
                bleep_count += 1
                start_sample = int(start_time * fps)
                end_sample = int(end_time * fps)
                duration = end_time - start_time
                
                # Overwrite audio samples with bleep track
                bleep_wave = generate_bleep_wave(duration, fps=fps)
                target_length = end_sample - start_sample
                audio_array[start_sample:end_sample] = bleep_wave[:target_length]

    # Render final output file
    if bleep_count > 0:
        new_audio = AudioArrayClip(audio_array, fps=fps)
        final_video = video.with_audio(new_audio)
        final_video.write_videofile(output_path, codec="libx264", audio_codec="aac", logger=None)
    else:
        video.write_videofile(output_path, codec="libx264", audio_codec="aac", logger=None)
        
    video.close()
    return bleep_count, full_transcript_data

# --- STREAMLIT UI ---

st.title("🎬 Local Auto Video Censoring Pipeline")
st.markdown("Upload any `.mp4` video to automatically detect and bleep out selected keywords entirely offline.")

# Sidebar Configurations
st.sidebar.header("🔧 Settings")
raw_bad_words = st.sidebar.text_area(
    "Words to Bleep (Comma Separated):", 
    value="swearword1, badword2, censor"
)
# Clean list inputs
banned_words = [w.strip().lower() for w in raw_bad_words.split(",") if w.strip()]

# File Uploader component
uploaded_file = st.file_uploader("Choose an MP4 Video File", type=["mp4"])

if uploaded_file is not None:
    st.success("Video uploaded successfully!")
    
    # Visual Layout Split (Left column for video preview, Right for processing)
    col1, col2 = st.columns(2)
    
    with col1:
        st.subheader("Original Video Preview")
        st.video(uploaded_file)

    with col2:
        st.subheader("Process Video")
        
        # Unique session state handling for buttons in Streamlit
        if st.button("🚀 Start Auto-Censoring", use_container_width=True):
            with st.spinner("Processing... AI is analyzing speech and editing audio layout..."):
                try:
                    # Write upload stream into a secure temporary file space
                    with tempfile.NamedTemporaryFile(delete=False, suffix=".mp4") as temp_in:
                        temp_in.write(uploaded_file.read())
                        temp_in_path = temp_in.name
                    
                    # Create temporary path output
                    temp_out_path = os.path.join(tempfile.gettempdir(), "censored_output.mp4")
                    
                    # Process pipeline
                    bleeps, transcript = process_video(temp_in_path, temp_out_path, banned_words)
                    
                    # Save results cleanly to state architecture
                    st.session_state['processed'] = True
                    st.session_state['bleep_count'] = bleeps
                    st.session_state['transcript'] = transcript
                    
                    # Read binary output block into memory buffer for local download actions
                    with open(temp_out_path, "rb") as f:
                        st.session_state['output_bytes'] = f.read()
                        
                    # Clean up temporary storage tracks
                    os.remove(temp_in_path)
                    os.remove(temp_out_path)
                    
                except Exception as e:
                    st.error(f"An error occurred during rendering: {e}")

        # If processing is complete, display transcript review and download button
        if st.session_state.get('processed', False):
            st.toast(f"Processing complete! Found {st.session_state['bleep_count']} instances.", icon="🤬")
            st.metric(label="Bleeps Applied", value=st.session_state['bleep_count'])
            
            # Download Widget Action
            st.download_button(
                label="📥 Download Censored MP4 Video",
                data=st.session_state['output_bytes'],
                file_name="censored_video.mp4",
                mime="video/mp4",
                use_container_width=True,
                type="primary"
            )
            
            # Transcript Review Section
            st.subheader("📝 Review Transcript Timeline")
            with st.expander("Click to expand full transcription breakdown", expanded=True):
                for item in st.session_state['transcript']:
                    time_stamp = f"[{item['start']:.2f}s - {item['end']:.2f}s]"
                    if item['censored']:
                        st.markdown(f"🔴 **{time_stamp} {item['word']}** *(Censored)*")
                    else:
                        st.markdown(f"⚪ `{time_stamp}` {item['word']}")
