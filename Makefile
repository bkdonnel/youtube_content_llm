.PHONY: help install start chat pipeline stats clean docker-build docker-chat docker-pipeline test-env

# Default target - show help
help:
	@echo "YouTube Music Production RAG System - Make Commands"
	@echo ""
	@echo "Quick Start:"
	@echo "  make start            Process new videos, then start chat interface"
	@echo ""
	@echo "Setup:"
	@echo "  make install          Install Python dependencies"
	@echo "  make test-env         Check if environment variables are set"
	@echo ""
	@echo "Individual Services:"
	@echo "  make chat             Start the FastAPI chat interface only"
	@echo "  make pipeline         Process new YouTube videos only"
	@echo "  make stats            View processing statistics"
	@echo "  make continuous       Run pipeline continuously (check every 60 min)"
	@echo ""
	@echo "Docker:"
	@echo "  make docker-build     Build Docker image"
	@echo "  make docker-chat      Run chat interface in Docker"
	@echo "  make docker-pipeline  Run pipeline in Docker"
	@echo ""
	@echo "Maintenance:"
	@echo "  make clean            Clean up temporary files"
	@echo "  make clean-all        Clean everything (including database)"
	@echo ""

# Install dependencies
install:
	@echo "Installing dependencies..."
	pip install -r requirements.txt
	@echo "Done! Make sure FFmpeg is installed (brew install ffmpeg on macOS)"

# Test environment variables
test-env:
	@echo "Checking environment variables..."
	@python -c "import os; from dotenv import load_dotenv; load_dotenv(); \
		keys = ['OPENAI_API_KEY', 'YOUTUBE_API_KEY', 'MILVUS_URI', 'MILVUS_TOKEN']; \
		missing = [k for k in keys if not os.getenv(k)]; \
		print('✅ All required variables set!' if not missing else f'❌ Missing: {missing}')"

# Start everything - process videos then start chat
start:
	@echo "=========================================="
	@echo "Step 1: Processing new YouTube videos..."
	@echo "=========================================="
	@python automated_pipeline.py
	@echo ""
	@echo "=========================================="
	@echo "Step 2: Starting chat interface..."
	@echo "=========================================="
	@echo "Access at http://localhost:8000"
	@echo ""
	@python main.py

# Start the chat interface
chat:
	@echo "Starting FastAPI chat interface..."
	@echo "Access at http://localhost:8000"
	python main.py

# Run the pipeline once
pipeline:
	@echo "Processing new YouTube videos..."
	python automated_pipeline.py

# View statistics
stats:
	@echo "Fetching statistics..."
	python automated_pipeline.py --stats

# Run pipeline continuously
continuous:
	@echo "Running pipeline continuously (checking every 60 minutes)..."
	@echo "Press Ctrl+C to stop"
	python automated_pipeline.py --continuous --interval 60

# Docker commands
docker-build:
	@echo "Building Docker image..."
	docker-compose build

docker-chat:
	@echo "Starting chat interface in Docker..."
	@echo "Access at http://localhost:8000"
	docker-compose up api

docker-pipeline:
	@echo "Running pipeline in Docker..."
	docker-compose run --rm pipeline

# Clean temporary files
clean:
	@echo "Cleaning up temporary files..."
	find music_tutorials -name "*.m4a" -type f -delete 2>/dev/null || true
	find music_tutorials -name "*.mp3" -type f -delete 2>/dev/null || true
	find music_tutorials -name "*.webm" -type f -delete 2>/dev/null || true
	find music_tutorials -name "*.info.json" -type f -delete 2>/dev/null || true
	find music_tutorials -name "*.webp" -type f -delete 2>/dev/null || true
	find music_tutorials -name "*.jpg" -type f -delete 2>/dev/null || true
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	@echo "Cleanup complete!"

# Clean everything including database
clean-all: clean
	@echo "Cleaning database and all data..."
	rm -rf database/video_tracker.db
	rm -rf music_tutorials/*/transcripts/*.json 2>/dev/null || true
	rm -rf music_tutorials/*/transcripts/*.txt 2>/dev/null || true
	@echo "Full cleanup complete!"

# Quick start - install and run chat
quickstart: install test-env chat

# Development - run both chat and continuous pipeline
dev:
	@echo "Starting development mode..."
	@echo "This will run the chat interface. Run 'make continuous' in another terminal for auto-processing."
	make chat
