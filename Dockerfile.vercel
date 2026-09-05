# Vercel container image for the Streamlit video-to-PDF application.
FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    STREAMLIT_SERVER_HEADLESS=true \
    STREAMLIT_BROWSER_GATHER_USAGE_STATS=false

WORKDIR /app

# ffmpeg lets yt-dlp merge common video/audio streams.  Tesseract enables the
# optional text-aware frame scoring used by video_processor.py.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates \
        ffmpeg \
        tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

COPY . ./

# Vercel routes traffic to port 80 by default.  ${PORT} also supports a port
# configured in Vercel project settings and local Docker testing.
EXPOSE 80
CMD ["sh", "-c", "streamlit run streamlit_app.py --server.address=0.0.0.0 --server.port=${PORT:-80} --server.headless=true --server.enableCORS=false --browser.gatherUsageStats=false"]
