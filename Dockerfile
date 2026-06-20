FROM python:3.12-slim

RUN apt-get update && apt-get install -y ffmpeg && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py app2.py app3.py badwords.txt streamlit-entrypoint.sh /app/
RUN chmod +x /app/streamlit-entrypoint.sh

EXPOSE 8501
WORKDIR /app
ENTRYPOINT ["/app/streamlit-entrypoint.sh"]
