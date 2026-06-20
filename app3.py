import os
import tempfile
import shutil
import subprocess
import numpy as np
import streamlit as st
from faster_whisper import WhisperModel
from moviepy.video.io.VideoFileClip import VideoFileClip
from moviepy.audio.AudioClip import AudioArrayClip

CACHE_DIR = os.path.expanduser("~/.cache/censor-app")
os.makedirs(CACHE_DIR, exist_ok=True)

for f in os.listdir(CACHE_DIR):
    p = os.path.join(CACHE_DIR, f)
    if os.path.isfile(p):
        os.remove(p)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
BADWORDS_FILE = os.path.join(SCRIPT_DIR, "badwords.txt")

def load_badwords():
    words = []
    if os.path.exists(BADWORDS_FILE):
        with open(BADWORDS_FILE) as f:
            for line in f:
                stripped = line.strip()
                if stripped and not stripped.startswith("#"):
                    words.append(stripped.lower())
    if not words:
        words = ["shit", "piss", "fuck", "cunt", "cocksucker", "motherfucker"]
    return words

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

def render_audio_only(input_path, words_timeline, padding=0.0):
    """Returns bleeped audio array without writing video."""
    video = VideoFileClip(input_path)
    fps = video.audio.fps
    total_samples = int(video.duration * fps)
    audio_array = video.audio.to_soundarray()
    video.close()

    for item in words_timeline:
        if item["censored"]:
            pad_samples = int(padding * fps)
            start_sample = max(0, int(item["start"] * fps) - pad_samples)
            end_sample = min(total_samples, int(item["end"] * fps) + pad_samples)
            target_length = end_sample - start_sample
            if target_length > 0:
                duration = target_length / fps
                bleep_wave = generate_bleep_wave(duration, fps=fps)
                if bleep_wave.shape[0] < target_length:
                    extra = np.zeros((target_length - bleep_wave.shape[0], 2))
                    bleep_wave = np.vstack((bleep_wave, extra))
                elif bleep_wave.shape[0] > target_length:
                    bleep_wave = bleep_wave[:target_length, :]
                audio_array[start_sample:end_sample] = bleep_wave

    return audio_array, fps


def render_censored_video(input_path, output_path, words_timeline, padding=0.0):
    """Applies bleeps to the video audio and replaces it via ffmpeg stream copy (no video re-encode)."""
    video = VideoFileClip(input_path)
    fps = video.audio.fps
    total_samples = int(video.duration * fps)
    audio_array = video.audio.to_soundarray()
    
    bleep_count = 0
    
    for item in words_timeline:
        if item["censored"]:
            bleep_count += 1
            pad_samples = int(padding * fps)
            start_sample = max(0, int(item["start"] * fps) - pad_samples)
            end_sample = min(total_samples, int(item["end"] * fps) + pad_samples)
            
            target_length = end_sample - start_sample
            if target_length > 0:
                duration = target_length / fps
                bleep_wave = generate_bleep_wave(duration, fps=fps)
                
                if bleep_wave.shape[0] < target_length:
                    extra = np.zeros((target_length - bleep_wave.shape[0], 2))
                    bleep_wave = np.vstack((bleep_wave, extra))
                elif bleep_wave.shape[0] > target_length:
                    bleep_wave = bleep_wave[:target_length, :]
                
                audio_array[start_sample:end_sample] = bleep_wave
    
    video.close()
    
    if bleep_count > 0:
        new_audio_clip = AudioArrayClip(audio_array, fps=fps)
        temp_audio = os.path.join(CACHE_DIR, "temp_censored_audio.wav")
        new_audio_clip.write_audiofile(temp_audio, logger=None)
        
        cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-i", temp_audio,
            "-c:v", "copy",
            "-c:a", "aac",
            "-map", "0:v:0",
            "-map", "1:a:0",
            output_path
        ]
        subprocess.run(cmd, capture_output=True)
        os.remove(temp_audio)
    else:
        shutil.copy2(input_path, output_path)
    
    return bleep_count

# --- STREAMLIT UI ---

st.title("🎬 Interactive Paragraph Auto-Censor")
st.markdown("Upload a video to auto-bleep words. Read the generated paragraph below to manually toggle any extra words.")

# Initialize session state architectures
if 'words_timeline' not in st.session_state:
    st.session_state['words_timeline'] = None
if 'temp_video_path' not in st.session_state:
    st.session_state['temp_video_path'] = None
if 'rendering_complete' not in st.session_state:
    st.session_state['rendering_complete'] = False
if 'final_output_bytes' not in st.session_state:
    st.session_state['final_output_bytes'] = None
if 'preview_audio_bytes' not in st.session_state:
    st.session_state['preview_audio_bytes'] = None
if 'preview_ready' not in st.session_state:
    st.session_state['preview_ready'] = False
if '_last_file_sig' not in st.session_state:
    st.session_state['_last_file_sig'] = None

# Load Whisper model at startup (cached, downloads on first run)
with st.sidebar:
    with st.status("Loading Whisper model...") as s:
        load_whisper_model()
        s.update(label="Whisper model ready", state="complete")

# Sidebar Configurations
st.sidebar.header("🔧 Initial Auto-Censor Settings")
default_words = load_badwords()
raw_bad_words = st.sidebar.text_area(
    "Automatic Banned Words (Comma Separated):",
    value=", ".join(default_words)
)
banned_words = [w.strip().lower() for w in raw_bad_words.split(",") if w.strip()]

bleep_padding = st.sidebar.slider(
    "Bleep Padding (seconds each side)",
    min_value=0.0, max_value=1.0, value=0.15, step=0.05,
    help="Extra time to bleep before and after each flagged word"
)

MAX_FILE_SIZE = 2 * 1024 * 1024 * 1024  # 2 GB

uploaded_file = st.file_uploader("Choose an MP4 Video File", type=["mp4"])

if uploaded_file is not None:
    if uploaded_file.size > MAX_FILE_SIZE:
        st.error(f"File too large ({uploaded_file.size / 1024**3:.1f} GB). Maximum is 2 GB.")
        st.stop()
    file_sig = f"{uploaded_file.name}:{uploaded_file.size}"
    if st.session_state.get('_last_file_sig') != file_sig:
        cached_path = os.path.join(CACHE_DIR, "uploaded_source.mp4")
        with open(cached_path, "wb") as f:
            f.write(uploaded_file.getvalue())
        st.session_state['temp_video_path'] = cached_path
        st.session_state['words_timeline'] = None
        st.session_state['rendering_complete'] = False
        st.session_state['final_output_bytes'] = None
        st.session_state['preview_audio_bytes'] = None
        st.session_state['preview_ready'] = False
        st.session_state['_last_file_sig'] = file_sig

    col1, col2 = st.columns([1, 1])

    with col1:
        st.subheader("Original Video")
        st.video(uploaded_file)

    with col2:
        st.subheader("1. Run Initial AI Scan")
        if st.button("Analyze Audio & Flag Words", use_container_width=True):
            with st.spinner("Whisper AI is creating transcription mapping timeline..."):
                st.session_state['words_timeline'] = analyze_speech(st.session_state['temp_video_path'], banned_words)
                st.session_state['rendering_complete'] = False

if st.session_state['words_timeline'] is not None:
    st.write("---")
    st.subheader("Interactive Review Paragraph")
    st.markdown("Click any word to toggle its censorship status.")

    word_container = st.container()

    with word_container:
        cols = st.columns(12)
        for index, item in enumerate(st.session_state['words_timeline']):
            col_idx = index % 12
            with cols[col_idx]:
                label_display = item["word"]
                if item["censored"]:
                    label_display = "BEEP " + label_display.strip()

                if st.button(label_display, key=f"word_btn_{item['id']}", use_container_width=True):
                    st.session_state['words_timeline'][index]['censored'] = not item['censored']
                    st.session_state['rendering_complete'] = False
                    st.rerun()

    st.write("---")
    st.subheader("🔇 Manual Timestamp Bleep")
    st.markdown("Add a bleep at any time range (in seconds) that Whisper may have missed.")
    mc1, mc2, mc3 = st.columns([2, 2, 1])
    with mc1:
        manual_start = st.number_input("Start (s)", min_value=0.0, step=0.1, format="%.2f", key="manual_start")
    with mc2:
        manual_end = st.number_input("End (s)", min_value=0.0, step=0.1, format="%.2f", key="manual_end")
    with mc3:
        st.write("")
        st.write("")
        if st.button("➕ Add", use_container_width=True):
            if manual_end > manual_start:
                existing_ids = {i["id"] for i in st.session_state['words_timeline']}
                new_id = min(existing_ids) - 1 if existing_ids else -1
                st.session_state['words_timeline'].append({
                    "id": new_id,
                    "word": f"[{manual_start:.2f}-{manual_end:.2f}s]",
                    "start": manual_start,
                    "end": manual_end,
                    "censored": True
                })
                st.session_state['words_timeline'].sort(key=lambda x: x["start"])
                st.session_state['rendering_complete'] = False
                st.rerun()
            else:
                st.error("End must be greater than start.")

    st.write("---")
    st.subheader("🎧 Preview Censored Audio")
    st.markdown("Listen to the bleeped audio before rendering the full video.")
    if st.button("Generate Audio Preview", use_container_width=True):
        with st.spinner("Generating audio preview..."):
            audio_arr, audio_fps = render_audio_only(st.session_state['temp_video_path'], st.session_state['words_timeline'], padding=bleep_padding)
            preview_path = os.path.join(CACHE_DIR, "preview_audio.wav")
            preview_clip = AudioArrayClip(audio_arr, fps=audio_fps)
            preview_clip.write_audiofile(preview_path, logger=None)
            with open(preview_path, "rb") as f:
                st.session_state['preview_audio_bytes'] = f.read()
            st.session_state['preview_ready'] = True
            st.rerun()

    if st.session_state.get('preview_ready'):
        st.audio(st.session_state['preview_audio_bytes'], format="audio/wav")

    st.write("---")
    st.subheader("2. Finalize Video Track Output")

    if st.button("Apply Review & Build Censored Video", type="primary", use_container_width=True):
        with st.spinner("Processing final video..."):
            temp_out_path = os.path.join(tempfile.gettempdir(), "final_interactive_output.mp4")

            bleeps_applied = render_censored_video(
                st.session_state['temp_video_path'],
                temp_out_path,
                st.session_state['words_timeline'],
                padding=bleep_padding
            )

            with open(temp_out_path, "rb") as f:
                st.session_state['final_output_bytes'] = f.read()

            st.session_state['rendering_complete'] = True
            st.session_state['total_applied_bleeps'] = bleeps_applied
            os.remove(temp_out_path)

    if st.session_state['rendering_complete']:
        st.success(f"Successfully processed! Final version contains {st.session_state['total_applied_bleeps']} bleeped audio sequences.")
        st.download_button(
            label="Download Censored Video MP4",
            data=st.session_state['final_output_bytes'],
            file_name="interactive_censored_video.mp4",
            mime="video/mp4",
            use_container_width=True
        )
