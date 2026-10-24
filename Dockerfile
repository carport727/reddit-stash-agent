FROM python:3.12-slim

# ffmpeg lets gallery-dl/yt-dlp merge Reddit video and audio streams.
RUN apt-get update \
    && apt-get install -y --no-install-recommends ffmpeg \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app app

ENV PYTHONUNBUFFERED=1 \
    CONFIG_FILE=/config/config.yaml \
    DATA_DIR=/data \
    LOG_DIR=/logs

EXPOSE 8787
VOLUME ["/config", "/data", "/logs"]

HEALTHCHECK --interval=60s --timeout=5s --start-period=20s \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8787/api/health', timeout=4)"

ENTRYPOINT ["python", "-m", "app.main"]
CMD ["serve"]
