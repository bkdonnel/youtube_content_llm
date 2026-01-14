# Local Development Setup Guide

This guide will help you run the YouTube Music Production RAG system locally on your machine.

## Prerequisites

1. **Python 3.11+**
   - Check: `python --version` or `python3 --version`

2. **FFmpeg** (required for audio processing)
   ```bash
   # macOS
   brew install ffmpeg

   # Ubuntu/Debian
   sudo apt-get install ffmpeg

   # Windows (via Chocolatey)
   choco install ffmpeg
   ```
   - Check: `ffmpeg -version`

3. **API Keys**
   - OpenAI API key (for Whisper transcription and embeddings)
   - YouTube Data API v3 key (for channel discovery)
   - Milvus/Zilliz Cloud credentials (for vector database)

## Installation Methods

You can run this project either **with Docker** (easier, no local Python setup needed) or **without Docker** (direct Python installation).

### Method 1: Docker (Recommended)

Docker handles all dependencies for you - no need to install Python, FFmpeg, or libraries manually.

**Prerequisites:**
- Docker and Docker Compose installed
- API keys configured in `.env` file

**Quick Start:**
```bash
# Build the Docker image
docker-compose build

# Run pipeline once to process videos
docker-compose run --rm pipeline

# Start the chat interface
docker-compose up api

# Or run both together (pipeline + API)
docker-compose up
```

See the "Running with Docker" section below for more details.

### Method 2: Direct Python Installation

Install dependencies directly on your machine.

## Step-by-Step Setup (Python Installation)

### 1. Clone and Install Dependencies

```bash
# Navigate to project directory
cd youtube_content_llm

# Create virtual environment (recommended)
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install Python dependencies
pip install -r requirements.txt
```

### 2. Configure Environment Variables

Your `.env` file should already have the necessary API keys configured:

```bash
# Verify your .env file has these keys set
cat .env
```

Required variables:
- `OPENAI_API_KEY` - Your OpenAI API key
- `YOUTUBE_API_KEY` - Your YouTube Data API v3 key
- `MILVUS_URI` - Your Zilliz Cloud endpoint
- `MILVUS_TOKEN` - Your Milvus authentication token

### 3. Test Your Setup

```bash
# Test that imports work
python -c "import yt_dlp; import openai; from pymilvus import connections; print('✅ All dependencies installed!')"

# Initialize the database (creates video_tracker.db)
python -c "from video_tracker import initialize_database; initialize_database(); print('✅ Database initialized!')"
```

## Running the System

### Option 1: Process Videos Once

Run the pipeline once to check for new videos and process them:

```bash
python automated_pipeline.py
```

This will:
1. Check YouTube channels for new videos (using YouTube API)
2. Download audio from new videos (using yt-dlp)
3. Transcribe audio (using OpenAI Whisper)
4. Upload segments to Milvus vector database
5. Clean up temporary files

**Note:** First run will process up to 5 videos per creator (configurable via `MAX_VIDEOS_PER_CHECK` in `.env`)

### Option 2: Continuous Monitoring

Run the pipeline continuously, checking for new videos every 60 minutes:

```bash
python automated_pipeline.py --continuous --interval 60
```

Press `Ctrl+C` to stop.

### Option 3: View Statistics

Check how many videos have been processed:

```bash
python automated_pipeline.py --stats
```

### Option 4: Start the Chat Interface

Start the FastAPI web server for the chat interface:

```bash
python main.py
```

Then open your browser to: http://localhost:8000

You can now ask questions about music production and the system will search through the processed video transcripts!

## Running with Docker

Docker is the easiest way to run this project as it handles all dependencies automatically.

### Build the Image

First, build the Docker image (only needed once, or after code changes):

```bash
docker-compose build
```

This creates a Docker image with Python 3.11, FFmpeg, and all required dependencies.

### Available Services

The `docker-compose.yml` defines several services you can run:

#### 1. **Pipeline** (Process Videos Once)
```bash
docker-compose run --rm pipeline
```
- Checks for new videos from configured YouTube channels
- Downloads, transcribes, and uploads to Milvus
- Exits when complete
- Use `--rm` to automatically remove container after completion

#### 2. **API Server** (Chat Interface)
```bash
docker-compose up api
```
- Starts the FastAPI server on http://localhost:8000
- Web chat interface for querying transcripts
- Runs in foreground (Ctrl+C to stop)
- Use `-d` flag to run in background: `docker-compose up -d api`

#### 3. **Full Stack** (Pipeline + API Together)
```bash
docker-compose up
```
- Runs both pipeline (continuous mode) and API server
- Pipeline checks for new videos periodically
- API server available on http://localhost:8000
- Both services run together

#### 4. **Download** (Legacy - Process All Creators)
```bash
docker-compose run --rm download
```
- Uses the standalone downloader script
- Processes all configured creators at once

### Docker Commands Reference

```bash
# Build/rebuild the image
docker-compose build

# Run pipeline once and exit
docker-compose run --rm pipeline

# Start API server (foreground)
docker-compose up api

# Start API server (background)
docker-compose up -d api

# Start both pipeline and API
docker-compose up

# Stop all running services
docker-compose down

# View logs
docker-compose logs -f

# View logs for specific service
docker-compose logs -f api

# Remove all containers and volumes
docker-compose down -v

# Run a command inside the container
docker-compose run --rm pipeline python automated_pipeline.py --stats

# Open a shell inside the container
docker-compose run --rm pipeline bash
```

### Accessing Files

The following directories are mounted as volumes, so files are accessible from your host machine:

- `./music_tutorials` - Downloaded audio and transcripts
- `./database` - SQLite database (`video_tracker.db`)

You can view these files on your machine even while Docker is running.

### Docker vs Direct Python

**Use Docker if:**
- You don't want to install Python/FFmpeg locally
- You want consistent environment across different machines
- You're deploying to production
- You prefer containerized applications

**Use Direct Python if:**
- You want faster iteration during development
- You already have Python 3.11+ installed
- You prefer seeing processes directly
- You want easier debugging

## Project Structure

```
youtube_content_llm/
├── automated_pipeline.py       # Main script for local development
├── main.py                     # FastAPI server for chat interface
├── youtube_transcript_downloader.py  # YouTube & transcription logic
├── add_transcripts_to_rag.py  # RAG integration logic
├── video_tracker.py            # SQLite database tracking
├── notifications.py            # Alert system (optional)
├── .env                        # Your environment variables
├── requirements.txt            # Python dependencies
├── music_tutorials/            # Output directory (created automatically)
│   ├── Zen_World/
│   │   └── transcripts/
│   └── Alice_Efe/
│       └── transcripts/
└── video_tracker.db            # SQLite database (created automatically)
```

## Configuration

### Add More Creators

Edit `youtube_transcript_downloader.py` to add more YouTube channels:

```python
CREATORS = {
    "Zen World": {
        "url": "https://www.youtube.com/@ZenWorld",
        "description": "Tech house and techno tutorials"
    },
    "Alice Efe": {
        "url": "https://www.youtube.com/@Alice-Efe",
        "description": "Music production tutorials"
    },
    # Add more:
    "Your Channel": {
        "url": "https://www.youtube.com/@YourChannel",
        "description": "Description here"
    }
}
```

### Adjust Processing Limits

Edit `.env` to change how many videos are processed per run:

```bash
MAX_VIDEOS_PER_CHECK=5       # Process up to 5 new videos per run
CHECK_INTERVAL_MINUTES=60    # Check every 60 minutes (continuous mode)
OUTPUT_DIR=music_tutorials   # Where to store files
```

## Troubleshooting

### YouTube API Errors

**Error:** `YOUTUBE_API_KEY not set`
- **Fix:** Make sure your `.env` file has `YOUTUBE_API_KEY=your_key_here`

**Error:** `Could not extract channel ID from URL`
- **Fix:** Verify the YouTube channel URL format is correct (e.g., `https://www.youtube.com/@ChannelName`)

### Download Errors

**Error:** `Sign in to confirm you're not a bot`
- **Fix:** This should not happen with YouTube Data API v3, but if it does, the system uses cookies for authentication. Set `YOUTUBE_COOKIES_B64` environment variable if needed.

**Error:** `FFmpeg not found`
- **Fix:** Install FFmpeg using the commands in Prerequisites section

### OpenAI API Errors

**Error:** `Incorrect API key provided`
- **Fix:** Verify your `OPENAI_API_KEY` in `.env` is correct and active

**Error:** `Rate limit exceeded`
- **Fix:** OpenAI has rate limits. Wait a few minutes and try again, or upgrade your OpenAI plan.

### Milvus Connection Errors

**Error:** `Failed to connect to Milvus`
- **Fix:** Check your `MILVUS_URI` and `MILVUS_TOKEN` are correct. Verify your Zilliz Cloud instance is active.

## What to Expect

### First Run
- The system will fetch up to 5 videos per creator (as configured)
- Each video takes ~1-3 minutes to process depending on length
- Audio files are deleted after transcription (saves disk space)
- Transcript files are uploaded to Milvus then deleted (saves disk space)

### Subsequent Runs
- Only NEW videos (not in `video_tracker.db`) are processed
- If no new videos found, the script completes quickly

### Costs
- **OpenAI Whisper:** ~$0.006 per minute of audio
- **OpenAI Embeddings:** ~$0.13 per 1M tokens (roughly 10,000 segments)
- **Milvus:** Free tier (1GB storage)

Example: Processing 5 x 20-minute videos = ~$0.60

## Next Steps

Once you have processed some videos locally:

1. **Test the Chat Interface:**
   ```bash
   python main.py
   ```
   Visit http://localhost:8000 and ask questions!

2. **Deploy to Cloud:**
   - See `ASTRONOMER_DEPLOYMENT.md` for Airflow deployment
   - See `CLAUDE.md` for FastAPI hosting options

3. **Add More Creators:**
   - Edit `youtube_transcript_downloader.py`
   - Run pipeline again to process their videos

## Getting Help

- **Project Documentation:** See `CLAUDE.md` for full system overview
- **Deployment Guide:** See `ASTRONOMER_DEPLOYMENT.md` for cloud deployment
- **Issues:** Check error messages in console output for specific guidance
