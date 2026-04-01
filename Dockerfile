FROM python:3.11-slim

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DEBIAN_FRONTEND=noninteractive \
    PORT=6990

# Set work directory
WORKDIR /app

# Install system dependencies for audio processing and ffmpeg
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    ffmpeg \
    libsndfile1 \
    ca-certificates \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/* /var/cache/apt/archives/*

# Copy requirements first for better caching
COPY requirements.txt .

# Upgrade pip and install Python dependencies
RUN pip install --upgrade pip setuptools wheel && \
    pip install -r requirements.txt

# Copy application code
COPY . .

# Create directories for runtime files
RUN mkdir -p config testing_chunks/live_chunks/raw testing_chunks/live_chunks/wav && \
    if [ -f uploaded_audio ]; then rm -f uploaded_audio; fi && \
    mkdir -p uploaded_audio && \
    chmod -R 755 config testing_chunks uploaded_audio

# Expose port
EXPOSE 6990

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=120s --retries=8 \
    CMD sh -c 'curl -fsS "http://127.0.0.1:${PORT:-6990}/healthz" > /dev/null || exit 1'

# Run the application with uvicorn
CMD ["sh", "-c", "uvicorn main:app --host 0.0.0.0 --port ${PORT:-6990}"]
