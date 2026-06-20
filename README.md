# Video Censor

Automatically detects and bleeds profanity in MP4 videos using Whisper speech-to-text. Runs as a Streamlit web app — upload a video, review the transcript, and download the censored version.

## Quick Start

```bash
git clone https://github.com/ProducerJenn/video-censor.git
cd video-censor
```

### Docker (Linux / macOS / Windows)

```bash
docker compose build
docker compose up -d
```

Open [http://localhost:8501](http://localhost:8501).

---

## Windows Setup (without Docker)

### 1. Install Python

Download and install **Python 3.12** from [python.org](https://www.python.org/downloads/).  
**Important:** check **"Add Python to PATH"** during installation.

### 2. Install ffmpeg

**Option A — via winget (easiest):**
```cmd
winget install ffmpeg
```

**Option B — manual install:**
1. Download the ffmpeg release build from [gyan.dev](https://www.gyan.dev/ffmpeg/builds/) (`ffmpeg-release-full.7z`)
2. Extract to `C:\ffmpeg`
3. Add `C:\ffmpeg\bin` to your system PATH (Settings → System → About → Advanced system settings → Environment Variables)

Verify it works:
```cmd
ffmpeg -version
```

### 3. Install Python packages

Open **Command Prompt** or **PowerShell** in the project folder:

```cmd
pip install faster-whisper==1.2.1 moviepy==2.2.1 numpy==2.4.6 streamlit==1.58.0
```

### 4. Run the app

```cmd
streamlit run app3.py --server.port=8501
```

Open [http://localhost:8501](http://localhost:8501).

### Docker Desktop (alternative)

If you prefer Docker on Windows:
1. Install [Docker Desktop for Windows](https://docs.docker.com/desktop/setup/install/windows-install/)
2. Make sure WSL 2 backend is enabled
3. From the project folder:

```cmd
docker compose build
docker compose up -d
```

---

## Usage

1. Drop an MP4 in the uploader
2. Bad words are loaded from `badwords.txt` (one per line, `#` for comments) — edit it freely
3. Click **Analyze Audio & Flag Words**
4. Review the transcript — click any word to toggle it on/off
5. Adjust **Bleep Padding** to extend the bleep before/after each word
6. Click **Apply Review & Build Censored Video**
7. Download the result

App3 also includes:
- **Audio Preview** — hear the bleeped audio before rendering the full video
- **Manual Timestamp Bleep** — bleep any time range Whisper might have missed

## Files

| File | Purpose |
|---|---|
| `app.py` | Basic: upload → auto-bleep → download |
| `app2.py` | Interactive: AI scan, clickable word review, then render |
| `app3.py` | **Default.** Same as app2 plus bleep padding, audio preview, manual timestamps |
| `badwords.txt` | Word list loaded on startup (one per line, `#` for comments) |
| `Dockerfile` | Python 3.12-slim + ffmpeg + deps |
| `docker-compose.yml` | Port 8501, auto-restart |

## Notes

- Whisper **base** model (~150 MB) is pre-downloaded during Docker build
- Set `WHISPER_MODEL=medium` env var (or build arg) to use the larger, more accurate model (~1.5 GB)
- Processing is CPU-bound; GPU acceleration is supported if you have CUDA set up
- Bleeped audio is a 1 kHz sine wave

## Credits

Coding and prompting by **Michael Robinson** — michael.robinson@armbian.com