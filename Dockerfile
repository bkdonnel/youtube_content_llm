# Local Development Dockerfile
# For Astronomer/Airflow deployment, use Dockerfile.astronomer

FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    build-essential \
    g++ \
    gcc \
    curl \
    unzip \
    && rm -rf /var/lib/apt/lists/*

# Install deno for yt-dlp JavaScript extraction
RUN curl -fsSL https://deno.land/install.sh | sh && \
    mv /root/.deno/bin/deno /usr/local/bin/deno

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Create output directories
RUN mkdir -p /app/music_tutorials /app/database

# Expose port for FastAPI
EXPOSE 8000

# Default command (can be overridden in docker-compose)
CMD ["python", "main.py"]
