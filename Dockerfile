# Use Python 3.11 slim image as base
FROM python:3.11-slim

# Install FFmpeg, build tools, and other system dependencies
RUN apt-get update && apt-get install -y \
    ffmpeg \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY *.py .
COPY templates/ templates/
COPY static/ static/

# Create output directory
RUN mkdir -p /app/music_tutorials

# Expose port for FastAPI (if running main.py)
EXPOSE 8000

# Default command (can be overridden)
CMD ["python", "automated_pipeline.py"]
