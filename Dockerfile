FROM python:3.12-slim

ARG WHISPER_MODEL=base

RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Pre-download Whisper model so it's ready on first use
RUN python -c "from faster_whisper import WhisperModel; WhisperModel('$WHISPER_MODEL', device='cpu', compute_type='int8')"

ENV WHISPER_MODEL=$WHISPER_MODEL

COPY app.py app2.py app3.py badwords.txt streamlit-entrypoint.sh /app/
RUN chmod +x /app/streamlit-entrypoint.sh

EXPOSE 8501
WORKDIR /app
ENTRYPOINT ["/app/streamlit-entrypoint.sh"]