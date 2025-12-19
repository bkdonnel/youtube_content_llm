# Music Production Tutorial RAG System

A comprehensive RAG (Retrieval-Augmented Generation) system that indexes music production tutorials from YouTube creators and enables semantic search across their content.

## 🎵 What is this?

This system allows you to:
- **Ask natural language questions** like "How to sidechain compress in FL Studio?" or "What are the best mixing techniques?"
- **Get precise answers** with exact timestamps from relevant tutorial videos
- **Search across hours** of content from top music production YouTubers
- **Automatically stay updated** as new tutorials are published

## 📋 Table of Contents

1. [Features](#features)
2. [Architecture](#architecture)
3. [Setup](#setup)
4. [Usage](#usage)
5. [Configuration](#configuration)
6. [Deployment](#deployment)
7. [Troubleshooting](#troubleshooting)

## ✨ Features

### Core Capabilities
- ✅ **Automated Video Processing** - Downloads and transcribes videos using OpenAI Whisper
- ✅ **Semantic Search** - Vector-based search using Milvus and OpenAI embeddings
- ✅ **Timestamp Attribution** - Get exact video timestamps for each answer
- ✅ **Web Interface** - Beautiful, responsive chat interface
- ✅ **Continuous Monitoring** - Automatically detects and processes new videos
- ✅ **Multi-Channel Support** - Tracks multiple YouTube creators simultaneously
- ✅ **Deduplication** - Avoids reprocessing the same content

### Supported Music Production Creators

The system currently tracks these YouTube channels:
- **In The Mix** - FL Studio tutorials
- **Busy Works Beats** - Music production for beginners
- **Simon Servida** - Ableton Live techniques
- **Reid Stefan** - Logic Pro and mixing
- **Andrew Huang** - Creative production and sound design
- **You Suck at Producing** - Ableton and electronic music
- **Venus Theory** - Synthesis and sound design

*You can easily add more creators in `youtube_transcript_downloader.py`*

## 🏗️ Architecture

### 3-Phase System

```
┌──────────────────┐      ┌──────────────────┐      ┌──────────────┐
│   PHASE 1:       │      │   PHASE 2:       │      │  PHASE 3:    │
│   Download &     │─────>│   RAG            │─────>│  Query &     │
│   Transcribe     │      │   Integration    │      │  Search      │
└──────────────────┘      └──────────────────┘      └──────────────┘
```

**Phase 1: Video Download & Transcription**
- Download audio from YouTube (yt-dlp)
- Transcribe with OpenAI Whisper
- Extract timed segments
- Save JSON + readable text files

**Phase 2: RAG Integration**
- Break transcripts into searchable segments
- Generate embeddings (text-embedding-3-large)
- Store in Milvus vector database
- Track processed videos in SQLite

**Phase 3: Query & Search**
- Web interface for user queries
- Semantic vector search in Milvus
- GPT-3.5-turbo for answer generation
- Display sources with timestamps

### Tech Stack

- **Backend**: FastAPI + Uvicorn
- **Vector DB**: Milvus (via Zilliz Cloud)
- **AI Models**: OpenAI (Whisper, Embeddings, GPT-3.5-turbo)
- **Video Processing**: yt-dlp, ffmpeg
- **Tracking**: SQLite
- **Frontend**: Vanilla JavaScript + CSS

## 🚀 Setup

### Prerequisites

- Python 3.8+
- ffmpeg installed
- OpenAI API key
- Milvus instance (free tier available at [Zilliz Cloud](https://cloud.zilliz.com))

### Installation

1. **Clone the repository**
```bash
git clone <your-repo-url>
cd youtube_content_llm
```

2. **Install dependencies**
```bash
# Install ffmpeg (macOS)
brew install ffmpeg

# Install ffmpeg (Ubuntu/Debian)
sudo apt update && sudo apt install ffmpeg

# Install Python packages
pip install -r requirements.txt
```

3. **Configure environment variables**

Create/update your `.env` file:
```bash
# OpenAI API
OPENAI_API_KEY=sk-your-openai-api-key-here

# Milvus Vector Database
# Sign up at https://cloud.zilliz.com for free tier
MILVUS_URI=your-milvus-instance-uri
MILVUS_TOKEN=your-milvus-token

# Pipeline Configuration
CHECK_INTERVAL_MINUTES=60
MAX_VIDEOS_PER_CHECK=5
OUTPUT_DIR=music_tutorials

# Optional: Notifications
# SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK
# DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR/WEBHOOK
```

4. **Setup Milvus (Vector Database)**

Sign up for a free account at [Zilliz Cloud](https://cloud.zilliz.com):
- Create a serverless cluster
- Copy the URI and API token
- Add them to your `.env` file

## 📖 Usage

### Option 1: Manual Processing

**Step 1: Download and transcribe videos**
```bash
python youtube_transcript_downloader.py
```

**Step 2: Start the API server**
```bash
python main.py
# Server runs at http://localhost:8000
```

**Step 3: Add transcripts to RAG**
```bash
# In a new terminal
python add_transcripts_to_rag.py
```

**Step 4: Open the web interface**
```
Open http://localhost:8000 in your browser
```

### Option 2: Automated Pipeline

**Run once (check for new videos)**
```bash
python automated_pipeline.py
```

**Run continuously (check every hour)**
```bash
python automated_pipeline.py --continuous --interval 60
```

**Show statistics**
```bash
python automated_pipeline.py --stats
```

### Example Queries

Try asking:
- "How to sidechain compress in FL Studio?"
- "What are the best EQ techniques for mixing?"
- "How to create a fat bass sound?"
- "What plugins does Andrew Huang recommend?"
- "How to master a track in Ableton?"

## ⚙️ Configuration

### Adding New Creators

Edit `youtube_transcript_downloader.py`:

```python
CREATORS = {
    "Your Creator Name": {
        "url": "https://www.youtube.com/@CreatorHandle",
        "description": "Creator description"
    },
    # Add more...
}
```

### Adjusting Pipeline Settings

In `.env`:
```bash
# How often to check for new videos (in minutes)
CHECK_INTERVAL_MINUTES=60

# Maximum videos to download per check
MAX_VIDEOS_PER_CHECK=5

# Output directory for transcripts
OUTPUT_DIR=music_tutorials
```

### Enabling Notifications

Uncomment and configure in `.env`:
```bash
# Slack
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL

# Discord
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR/WEBHOOK

# Email
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SENDER_EMAIL=your-email@gmail.com
SENDER_PASSWORD=your-app-password
RECIPIENT_EMAIL=notify@example.com
```

## 🚀 Deployment

### Option A: Local Development

```bash
# Terminal 1: Run API server
python main.py

# Terminal 2: Run pipeline (optional)
python automated_pipeline.py --continuous --interval 60
```

### Option B: Background Process (Linux/Mac)

```bash
# Using screen
screen -S music-pipeline
python automated_pipeline.py --continuous --interval 60
# Press Ctrl+A then D to detach

# Reattach later
screen -r music-pipeline
```

### Option C: Systemd Service (Linux)

Create `/etc/systemd/system/music-pipeline.service`:
```ini
[Unit]
Description=Music Production Pipeline
After=network.target

[Service]
Type=simple
User=your_username
WorkingDirectory=/path/to/youtube_content_llm
Environment="PATH=/path/to/venv/bin:/usr/local/bin"
ExecStart=/path/to/venv/bin/python automated_pipeline.py --continuous --interval 60
Restart=always

[Install]
WantedBy=multi-user.target
```

Enable and start:
```bash
sudo systemctl enable music-pipeline
sudo systemctl start music-pipeline
sudo systemctl status music-pipeline
```

### Option D: Cron Job

Add to crontab:
```bash
# Check every hour
0 * * * * cd /path/to/project && /path/to/venv/bin/python automated_pipeline.py >> /var/log/pipeline.log 2>&1
```

## 📁 File Structure

```
youtube_content_llm/
├── main.py                          # FastAPI server
├── youtube_transcript_downloader.py # Download & transcribe videos
├── add_transcripts_to_rag.py       # RAG integration
├── automated_pipeline.py            # Automated continuous processing
├── video_tracker.py                 # SQLite tracking database
├── notifications.py                 # Alert system
├── requirements.txt                 # Python dependencies
├── .env                             # Configuration (not in git)
├── templates/
│   └── index.html                   # Web interface
├── static/
│   ├── css/style.css               # Styles
│   └── js/chat.js                  # Frontend logic
├── music_tutorials/                 # Generated content
│   ├── In_The_Mix/
│   │   └── transcripts/
│   ├── Busy_Works_Beats/
│   │   └── transcripts/
│   └── ...
├── video_tracker.db                 # Processing history
├── YOUTUBE_TRANSCRIBER_README.md   # Architecture docs
└── CONVERT_TO_PIPELINE.md          # Pipeline guide
```

## 🐛 Troubleshooting

### Common Issues

**1. "OPENAI_API_KEY not found"**
```bash
# Check .env file
cat .env | grep OPENAI_API_KEY

# Make sure it's loaded
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print(os.getenv('OPENAI_API_KEY'))"
```

**2. "Milvus connection failed"**
- Verify you've signed up at https://cloud.zilliz.com
- Check MILVUS_URI and MILVUS_TOKEN in `.env`
- Test connection:
```python
from pymilvus import MilvusClient
client = MilvusClient(uri='YOUR_URI', token='YOUR_TOKEN')
print(client.list_collections())
```

**3. "ffmpeg not found"**
```bash
# Verify installation
ffmpeg -version

# Install if missing
# macOS: brew install ffmpeg
# Linux: sudo apt install ffmpeg
```

**4. "YouTube video not accessible"**
```bash
# Update yt-dlp
pip install --upgrade yt-dlp

# Test manually
yt-dlp --list-formats "https://youtube.com/watch?v=VIDEO_ID"
```

**5. "Rate limit exceeded" (OpenAI)**
- Add delays between API calls
- Upgrade to higher API tier
- Reduce MAX_VIDEOS_PER_CHECK

### Getting Help

Check the detailed documentation:
- `YOUTUBE_TRANSCRIBER_README.md` - Full architecture guide
- `CONVERT_TO_PIPELINE.md` - Pipeline automation guide

## 💰 Cost Estimates

Based on 100 videos/month:

**OpenAI API:**
- Whisper transcription: ~$18/month
- Embeddings: ~$0.65/month
- Chat completions: ~$2/month
- **Total: ~$21/month**

**Milvus (Zilliz Cloud):**
- Free tier: 1M vectors, sufficient for 1000+ videos
- **Cost: $0/month**

**Total: ~$21/month for 100 videos**

## 📚 Additional Resources

- [OpenAI API Documentation](https://platform.openai.com/docs)
- [Milvus Documentation](https://milvus.io/docs)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)
- [yt-dlp Documentation](https://github.com/yt-dlp/yt-dlp)

## 🤝 Contributing

Feel free to add more music production creators, improve the search algorithm, or enhance the UI!

## 📄 License

MIT

## 🙏 Acknowledgments

- Built using the architecture outlined in `YOUTUBE_TRANSCRIBER_README.md`
- Music production community for amazing educational content
