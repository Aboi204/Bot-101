FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8000

# Install runtime dependencies: ffmpeg, libopus, libsodium, git
RUN apt-get update && apt-get install -y --no-install-recommends \
    ffmpeg \
    libopus0 \
    libsodium23 \
    git \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Copy dependencies first for Docker caching
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code and directories
COPY src/ ./src/
COPY cookies/ ./cookies/
COPY .agents/ ./.agents/
COPY .env* ./

# Expose Keep-Alive HTTP health port
EXPOSE 8000

# Run unprivileged user for security
RUN useradd -m botuser && chown -R botuser:botuser /app
USER botuser

CMD ["python", "src/bot.py"]
