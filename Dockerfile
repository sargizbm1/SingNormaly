FROM python:3.12-slim

WORKDIR /app

# ffmpeg is not strictly required (Lavalink handles decoding) but is kept
# for compatibility with any local audio utilities you may add later.
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Config/data are meant to be provided at runtime (see docker-compose.yml),
# not baked into the image.
VOLUME ["/app/data", "/app/logs"]

CMD ["python", "-m", "bot.main"]
