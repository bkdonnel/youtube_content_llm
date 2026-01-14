# YouTube Music Production RAG System

## Project Overview

This project is an **end-to-end Retrieval Augmented Generation (RAG) system** that processes YouTube music production channels, downloads videos, transcribes them using OpenAI Whisper, and makes the content searchable through a conversational AI interface.

**Key Features:**
- YouTube video processing on-demand
- Audio transcription using OpenAI Whisper API
- Semantic search with Milvus vector database
- ChatGPT-powered conversational interface
- Simple local execution - run when you need it

## Recent Updates (v2.0.0 - January 13, 2026)

### Simplified Architecture
- **Removed:** Airflow and cloud deployment complexity
- **New approach:** Simple local execution - run the pipeline when you need it
- **Benefit:** No 24/7 services required, no bot detection issues

### YouTube Data API v3 Integration
- **Fixed:** Bot detection error ("Sign in to confirm you're not a bot") when scraping YouTube channels
- **Implementation:** Uses official YouTube Data API v3 for channel discovery
- **Benefits:**
  - Reliable channel discovery without bot detection
  - Better rate limits and quota management
  - Proper ISO 8601 duration parsing for filtering shorts
  - Official Google API support

### Active Creators
- **Zen World** - Tutorials on arrangement, sound design, tech house and techno
- **Alice Efe** - Music production tutorials

### Technical Stack
- `google-api-python-client` for YouTube Data API v3
- `pymilvus` 2.4.0 for vector database
- `openai` for Whisper transcription and embeddings
- `yt-dlp` for audio downloads
- `FastAPI` for chat interface

## What It Does

### User Experience
Users can ask questions about music production techniques (e.g., "How to sidechain compress in FL Studio?") and receive:
1. **AI-generated answers** based on actual YouTube tutorial content
2. **Source citations** with direct links to specific video timestamps
3. **Formatted responses** with markdown styling (bold, lists, code blocks)

### Manual Processing Pipeline
When you run the pipeline manually, it:
1. Checks YouTube channels for new videos
2. Downloads audio from new videos
3. Transcribes audio to text with timestamps
4. Breaks transcripts into searchable segments
5. Converts segments to vector embeddings
6. Stores embeddings in Milvus vector database
7. Cleans up temporary files

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                         USER INTERFACE                          │
│                    (Web Chat @ localhost:8000)                  │
└────────────────────────────┬────────────────────────────────────┘
                             │
                    ┌────────▼─────────┐
                    │   FastAPI Server  │
                    │    (main.py)      │
                    └────────┬──────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
              ▼              ▼              ▼
        ┌──────────┐   ┌──────────┐   ┌──────────┐
        │ OpenAI   │   │  Milvus  │   │ YouTube  │
        │Embedding │   │  Vector  │   │ Data API │
        │   API    │   │   DB     │   │    v3    │
        └──────────┘   └──────────┘   └──────────┘

┌─────────────────────────────────────────────────────────────────┐
│                    MANUAL PROCESSING PIPELINE                   │
│                   (automated_pipeline.py)                       │
└────────────────────────────┬────────────────────────────────────┘
                             │
              ┌──────────────┼──────────────┐
              │              │              │
              ▼              ▼              ▼
        ┌──────────┐   ┌──────────┐   ┌──────────┐
        │ YouTube  │   │ OpenAI   │   │ SQLite   │
        │Data API  │   │ Whisper  │   │ Tracker  │
        │   v3     │   │   API    │   │    DB    │
        └──────────┘   └──────────┘   └──────────┘
                             │
                             ▼
                       ┌──────────┐
                       │  Milvus  │
                       │  Vector  │
                       │    DB    │
                       └──────────┘
```

## Data Flow

### 1. Content Ingestion Flow

```
YouTube Creator Upload
    ↓
Run automated_pipeline.py (manual execution)
    ↓
Fetch channel videos via YouTube Data API v3
    ↓
Filter out YouTube Shorts (≤60 seconds)
    ↓
Check video_tracker.db for already processed videos
    ↓
Download audio from new videos (.m4a file via yt-dlp)
    ↓
Transcribe with Whisper (OpenAI API)
    ↓
Save transcript JSON with timestamps
    ↓
Break into segments (add_transcripts_to_rag.py)
    ↓
Generate embeddings (OpenAI text-embedding-3-large)
    ↓
Upload to Milvus (Zilliz Cloud)
    ↓
Mark as processed (video_tracker.db)
    ↓
Delete temporary files (audio, transcript JSON)
```

### 2. Query Flow

```
User asks question
    ↓
Generate query embedding (OpenAI)
    ↓
Search Milvus for similar segments (COSINE similarity)
    ↓
Retrieve top 5 most relevant segments
    ↓
Format as context for GPT
    ↓
Generate answer (GPT-3.5-turbo)
    ↓
Return answer + source citations
    ↓
Display in web interface with markdown formatting
```

## Key Components

### Core Python Modules

#### `main.py` - FastAPI Backend
- **Purpose:** Web server and RAG API
- **Endpoints:**
  - `GET /` - Web interface
  - `POST /api/chat` - Main chat endpoint
  - `POST /api/add-document` - Add segments to RAG
  - `GET /api/health` - Health check
  - `GET /api/stats` - Collection statistics
- **Technologies:** FastAPI, Uvicorn, Jinja2
- **Port:** 8000

#### `youtube_transcript_downloader.py` - YouTube Processing
- **Purpose:** Download and transcribe YouTube videos
- **Key Functions:**
  - `get_channel_videos()` - Fetch video metadata using YouTube Data API v3
  - `get_channel_id_from_url()` - Extract channel ID from YouTube URLs
  - `parse_duration()` - Parse ISO 8601 durations to filter shorts
  - `download_video_audio()` - Download audio using yt-dlp
  - `generate_transcript_with_chunking()` - Transcribe with Whisper
  - `save_transcript_json()` - Save transcript data
- **Configuration:** `CREATORS` dict defines monitored channels
- **Current Creators:** Zen World, Alice Efe
- **API:** Uses YouTube Data API v3 for reliable channel scraping (avoids bot detection)

#### `add_transcripts_to_rag.py` - RAG Integration
- **Purpose:** Process transcripts and upload to Milvus
- **Key Functions:**
  - `create_segments_from_transcript()` - Break into searchable chunks
  - `process_transcript_file()` - Upload segments to RAG
  - `generate_embedding()` - Create vector embeddings
- **Segment Format:** `[MM:SS-MM:SS] transcript text`

#### `video_tracker.py` - Processing State Management
- **Purpose:** Track which videos have been processed
- **Database:** SQLite (`video_tracker.db`)
- **Tables:**
  - `processed_videos` - Video processing status
  - `channel_checks` - Last check timestamps
  - `processing_errors` - Error logs
- **Key Functions:**
  - `is_video_processed()` - Check if video already processed
  - `mark_video_processed()` - Record processed video
  - `mark_rag_integrated()` - Mark as uploaded to Milvus

#### `notifications.py` - Alert System
- **Purpose:** Send notifications on events
- **Supported Channels:**
  - Slack webhook
  - Discord webhook
  - Email (SMTP)
- **Events:**
  - New video processed
  - Processing errors

#### `automated_pipeline.py` - Main Processing Pipeline
- **Purpose:** Process new YouTube videos and add to RAG system
- **Mode:** Can run once or continuously
- **Usage:**
  - Single run: `python automated_pipeline.py`
  - Continuous: `python automated_pipeline.py --continuous --interval 60`
  - Statistics: `python automated_pipeline.py --stats`
- **When to use:** Run manually whenever you want to check for and process new videos

### Frontend Components

#### `templates/index.html` - Web Interface
- **Purpose:** Chat interface HTML
- **Features:**
  - Chat message display
  - Input field with send button
  - Sources sidebar with video links
  - Example query buttons
  - Status indicator

#### `static/js/chat.js` - Chat Application Logic
- **Purpose:** Frontend JavaScript for chat functionality
- **Features:**
  - Message sending/receiving
  - Markdown rendering (marked.js)
  - Typing indicators
  - Source display with YouTube timestamps
  - Conversation history management

#### `static/css/style.css` - Styling
- **Purpose:** UI styling and layout
- **Features:**
  - Gradient background
  - Message bubbles
  - Markdown formatting styles
  - Responsive design
  - Animation effects

### Configuration Files

#### `requirements.txt` - Python Dependencies
```
python-dotenv>=1.0.0                # Environment variables
yt-dlp>=2023.11.16                  # YouTube downloads
openai>=1.3.0                       # OpenAI API (Whisper, Embeddings, GPT)
google-api-python-client>=2.108.0   # YouTube Data API v3
pymilvus>=2.4.0                     # Milvus vector database
grpcio-tools                        # Pre-built wheels for gRPC
httpx==0.25.2                       # HTTP client
mmh3==3.0.0                         # Hashing for deduplication
pydantic>=2.5.0                     # Data validation
```

#### `Dockerfile` - Container Configuration
- **Base Image:** `python:3.11-slim`
- **System Packages:** FFmpeg for audio processing
- **Purpose:** Optional Docker container for local development
- **Note:** Can run directly with Python, Docker is optional

#### `.env` - Environment Variables
```
OPENAI_API_KEY            # OpenAI API credentials
YOUTUBE_API_KEY           # YouTube Data API v3 key (for channel discovery)
MILVUS_URI                # Zilliz Cloud endpoint
MILVUS_TOKEN              # Milvus authentication
OUTPUT_DIR                # Where to store files (default: music_tutorials)
MAX_VIDEOS_PER_CHECK      # Process limit per run (default: 5)
CHECK_INTERVAL_MINUTES    # Polling frequency (default: 60)
RAG_API_URL               # RAG API endpoint (default: http://localhost:8000)
```

## Database Schema

### Milvus Collection: `music_production_tutorials`

**Fields:**
- `id` (int): Hash of text content (for deduplication)
- `text` (varchar): Transcript segment with timestamp
- `vector` (float[3072]): Embedding from text-embedding-3-large
- `channel_name` (varchar): YouTube channel name
- `metadata` (varchar): JSON string with video info

**Metadata Structure:**
```json
{
  "channel_name": "Zen World",
  "video_title": "How to Mix Techno",
  "youtube_id": "abc123xyz",
  "start_time": 120.5,
  "end_time": 145.2,
  "duration": 24.7,
  "segment_type": "transcript_segment",
  "source": "youtube_video",
  "language": "en",
  "timestamp": "[02:00-02:25]"
}
```

**Index:** COSINE similarity on vector field

### SQLite Database: `video_tracker.db`

**Table: processed_videos**
- `video_id` (TEXT PRIMARY KEY)
- `channel_name` (TEXT)
- `video_title` (TEXT)
- `upload_date` (TEXT)
- `processed_date` (TIMESTAMP)
- `transcript_path` (TEXT)
- `rag_integrated` (BOOLEAN)

**Table: channel_checks**
- `channel_name` (TEXT PRIMARY KEY)
- `last_check` (TIMESTAMP)
- `last_video_id` (TEXT)

**Table: processing_errors**
- `id` (INTEGER PRIMARY KEY)
- `video_id` (TEXT)
- `channel_name` (TEXT)
- `error_message` (TEXT)
- `error_date` (TIMESTAMP)

## Technology Stack

### AI/ML Services
- **OpenAI Whisper API** - Audio transcription
- **OpenAI text-embedding-3-large** - Vector embeddings (3072 dimensions)
- **OpenAI GPT-3.5-turbo** - Response generation
- **Milvus/Zilliz Cloud** - Vector database (free tier, 1GB)

### Backend
- **FastAPI** - Web framework
- **Uvicorn** - ASGI server
- **Pydantic** - Data validation
- **Python 3.11** - Runtime

### Frontend
- **Jinja2** - HTML templating
- **Marked.js** - Markdown parser
- **Vanilla JavaScript** - No frameworks
- **CSS3** - Styling with gradients and animations

### Data Processing
- **YouTube Data API v3** - Channel discovery and video metadata
- **google-api-python-client** - YouTube API client library
- **yt-dlp** - YouTube video/audio downloads
- **FFmpeg** - Audio processing and chunking
- **PyMilvus** - Milvus Python client
- **SQLite** - Local state tracking

### Cloud Services
- **Zilliz Cloud** - Hosted Milvus (GCP us-west-1)
- **OpenAI API** - AI services (Whisper, Embeddings, GPT)
- **YouTube Data API v3** - Video metadata and channel information

## Storage Strategy

### What Gets Stored Where

**Milvus (Permanent):**
- ✅ Vector embeddings (searchable)
- ✅ Transcript segments with timestamps
- ✅ Video metadata
- **Size:** ~15 KB per segment
- **Capacity:** ~66,000 segments (free tier)

**SQLite (Persistent):**
- ✅ Video processing status
- ✅ Channel check timestamps
- ✅ Error logs
- **Size:** <1 MB
- **Location:** Container filesystem (ephemeral in cloud)

**Temporary Storage (Deleted After Processing):**
- ❌ Audio files (.m4a) - deleted after transcription
- ❌ Transcript JSON files - deleted after upload to Milvus
- ❌ Readable text files - deleted after upload

**Not Stored:**
- ❌ Video files (only audio downloaded)
- ❌ YouTube thumbnails (only URLs stored)
- ❌ Raw Whisper API responses (processed then discarded)

### Why No S3?

**Decision:** Store only in Milvus, no separate file storage

**Rationale:**
1. Milvus already contains all searchable data
2. Transcript files never accessed after RAG upload
3. Saves storage costs (~$0.02/month avoided)
4. Simpler architecture

**Trade-off:** Can't review original transcript files later (would need to re-transcribe)

## How to Use

### Prerequisites

1. Python 3.11+
2. FFmpeg installed (`brew install ffmpeg` on macOS, `apt-get install ffmpeg` on Linux)
3. Required API keys in `.env` file:
   - `OPENAI_API_KEY` - OpenAI API key
   - `YOUTUBE_API_KEY` - YouTube Data API v3 key (get from Google Cloud Console)
   - `MILVUS_URI` and `MILVUS_TOKEN` - Zilliz Cloud credentials

### Setup

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Verify environment variables are set
cat .env

# 3. Initialize database (optional - will auto-create)
python -c "from video_tracker import initialize_database; initialize_database()"
```

### Running the System

**Option 1: Chat Interface Only (Query Existing Data)**

```bash
# Start FastAPI server for chat interface
python main.py
# Access at http://localhost:8000
```

This queries the existing data in Milvus. No YouTube access needed.

**Option 2: Process New Videos**

```bash
# Run pipeline once to check for and process new videos
python automated_pipeline.py

# View statistics
python automated_pipeline.py --stats

# Run continuously (check every 60 minutes)
python automated_pipeline.py --continuous --interval 60
```

**Option 3: Using Docker Compose (Optional)**

```bash
# Build the image
docker-compose build

# Run pipeline once
docker-compose run --rm pipeline

# Start API server
docker-compose up api

# Stop services
docker-compose down
```

### Important Notes

- The pipeline creates a local `video_tracker.db` SQLite database
- Audio and transcript files are stored temporarily in `music_tutorials/` directory
- Temporary files are automatically deleted after processing
- All searchable data is permanently stored in Milvus (Zilliz Cloud)

## Configuration

### Adding New Creators

Edit `include/youtube_transcript_downloader.py`:

```python
CREATORS = {
    "Zen World": {
        "url": "https://www.youtube.com/@ZenWorld",
        "description": "Tutorials on arrangement, sound design, tech house and techno"
    },
    "Alice Efe": {
        "url": "https://www.youtube.com/@Alice-Efe",
        "description": "Music production tutorials"
    },
    # Add more creators:
    "In The Mix": {
        "url": "https://www.youtube.com/@inthemix",
        "description": "Mixing and mastering tutorials"
    },
    "Venus Theory": {
        "url": "https://www.youtube.com/@VenusTheory",
        "description": "Music production and synthesis"
    }
}
```

Then run `python automated_pipeline.py` to process videos from the new creators.

### Adjusting Processing Limits

Edit `.env` file:
```
MAX_VIDEOS_PER_CHECK=10  # Process up to 10 videos per run
```

## Cost Analysis

### Monthly Costs

**OpenAI API:**
- Whisper transcription: ~$0.006/minute of audio
- Embeddings: ~$0.13 per 1M tokens (~10,000 segments)
- GPT-3.5 chat: ~$0.002 per 1K tokens
- **Estimated:** $5-15/month (depends on how many videos you process)

**Milvus (Zilliz Cloud):**
- Free tier: 1 GB storage
- Current usage: ~0.5% of limit
- **Cost:** $0/month (free)

**YouTube Data API v3:**
- Free tier: 10,000 quota units/day
- Typical usage: ~100-500 units/day
- **Cost:** $0/month (free)

**Total Monthly Cost:** $5-15/month (OpenAI only)

## Current Status

### Active Components
- Milvus database (Zilliz Cloud, free tier)
- YouTube Data API v3 integration (no bot detection issues)
- Local execution (run when needed)
- FastAPI chat interface

### Data Status
- **Creators:** 2 (Zen World, Alice Efe)
- **Videos processed:** ~5-10
- **Segments in Milvus:** ~250-500
- **Storage used:** ~3.75-7.5 MB (~0.5% of limit)
- **Execution:** Manual (run when you want new videos)

## Future Enhancements

### Potential Improvements
1. **Add more creators** - Expand to 10-20 music production channels
2. **Deploy API to cloud** - Railway/Render for public access
3. **Add authentication** - Secure the chat interface
4. **Improve embeddings** - Try different chunking strategies
5. **Add analytics** - Track popular queries and sources
6. **Video summarization** - Generate video summaries with GPT-4
7. **Multi-language support** - Transcribe non-English content
8. **User feedback loop** - Let users rate answer quality
9. **Cloud database** - Replace SQLite with PostgreSQL
10. **S3 archival** - Optional backup of transcripts to AWS S3

### Scalability Considerations
- **Milvus free tier limit:** Can store ~330-660 full videos
- **OpenAI rate limits:** May need to throttle for high volume
- **Cost optimization:** Consider switching to GPT-4o-mini for chat responses

## Development Workflow

### Local Development Cycle
```bash
# 1. Make changes to code
vim main.py

# 2. Test the chat interface
python main.py

# 3. Test the pipeline
python automated_pipeline.py --stats

# 4. Process new videos
python automated_pipeline.py
```

### File Organization
```
youtube_content_llm/
├── include/                                 # Helper modules
│   ├── __init__.py
│   ├── youtube_transcript_downloader.py     # YouTube processing with API
│   ├── add_transcripts_to_rag.py           # RAG integration
│   ├── video_tracker.py                    # SQLite tracking
│   └── notifications.py                    # Alerts (Slack/Discord/Email)
├── static/                                  # Frontend assets
│   ├── css/style.css
│   └── js/chat.js
├── templates/                               # HTML templates
│   └── index.html
├── music_tutorials/                         # Local output (gitignored)
│   ├── Zen_World/
│   │   └── transcripts/
│   └── Alice_Efe/
│       └── transcripts/
├── database/                                # SQLite databases
│   └── video_tracker.db
├── main.py                                  # FastAPI server
├── youtube_transcript_downloader.py         # Legacy (use include/ version)
├── add_transcripts_to_rag.py               # Legacy (use include/ version)
├── video_tracker.py                        # Legacy (use include/ version)
├── notifications.py                        # Legacy (use include/ version)
├── automated_pipeline.py                   # Main processing pipeline
├── requirements.txt                        # Python dependencies
├── Dockerfile                              # Docker image (optional)
├── docker-compose.yml                      # Docker orchestration (optional)
├── .env                                    # Environment variables (gitignored)
├── .dockerignore                           # Docker build exclusions
├── CLAUDE.md                               # This file (comprehensive guide)
├── LOCAL_SETUP.md                          # Local development setup guide
└── README.md                               # Project documentation
```

## Troubleshooting

### Common Issues

**Milvus Connection Errors:**
- Check `MILVUS_URI` and `MILVUS_TOKEN` in `.env` file
- Verify Zilliz Cloud instance is active
- Check firewall/network connectivity

**OpenAI API Errors:**
- Verify `OPENAI_API_KEY` is set correctly in `.env` file
- Check API quota and billing at platform.openai.com
- Review rate limits for Whisper/Embeddings/Chat

**Audio Download Failures:**
- Check YouTube video availability
- Verify FFmpeg is installed (`brew install ffmpeg` on macOS)
- Check disk space for temp files in `music_tutorials/` directory

**YouTube Bot Detection Error:**
- Error: "Sign in to confirm you're not a bot"
- **Cause:** yt-dlp scraping detected as bot activity
- **Fix:** System uses YouTube Data API v3 for channel discovery
- Ensure `YOUTUBE_API_KEY` is set in `.env` file
- Bot detection only affects audio downloads, not channel discovery

**Environment Variables Not Loading:**
- Make sure all required variables are in `.env` file
- Verify `.env` file is in the project root directory
- Restart the application after changing `.env` file

**Transcription Timeouts:**
- Large videos may take 10+ minutes
- System automatically chunks large audio files
- Check OpenAI API status if experiencing delays

## Support & Resources

### Documentation
- **Milvus Docs:** https://milvus.io/docs/
- **FastAPI Docs:** https://fastapi.tiangolo.com/
- **OpenAI API Docs:** https://platform.openai.com/docs/
- **YouTube Data API v3:** https://developers.google.com/youtube/v3

### Service URLs
- **Zilliz Cloud:** https://cloud.zilliz.com
- **OpenAI Platform:** https://platform.openai.com
- **Google Cloud Console:** https://console.cloud.google.com

---

**Last Updated:** January 13, 2026
**Version:** 2.0.0
**Status:** Active (Local Execution)
