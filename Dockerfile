# Use official Python slim image (Debian-based, smaller than full python image)
FROM python:3.11-slim

# Set working directory inside container
WORKDIR /app

# Install system dependencies needed by Pyrogram / cryptography / etc.
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    libffi-dev \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip and install requirements in one layer
COPY requirements.txt .
RUN pip install --no-cache-dir -U pip && \
    pip install --no-cache-dir -r requirements.txt

# Copy the actual bot code
COPY . .

# Make sure sessions & database folders exist and are writable
RUN mkdir -p sessions database && \
    chmod -R 777 sessions database

# Environment variables (you can override them at runtime)
ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    API_ID=your_api_id_here \
    API_HASH=your_api_hash_here \
    BOT_TOKEN=your_bot_token_here

# The bot writes sessions + database.db in current directory
VOLUME ["/app/sessions", "/app/database"]

# Start the bot
CMD ["python", "bot.py"]
