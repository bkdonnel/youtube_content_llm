# YouTube Music Production RAG System

Ask questions about music production and get answers from YouTube tutorials, with direct links to the exact video timestamps.

## What Does This Do?

This system lets you search through music production tutorials using natural language. Instead of watching hours of videos, ask a question like:

- "How do I sidechain compress in FL Studio?"
- "What's the best way to EQ vocals?"
- "How do I create a techno bassline?"

You get an AI-generated answer based on actual tutorial content, plus clickable links to the specific moments in the videos where the topic is discussed.

## Quick Start

### 1. Prerequisites

Before you begin, make sure you have:

- **Python 3.11+** installed
- **FFmpeg** installed for audio processing
- **API Keys** (see step 3 below)

Install FFmpeg:
```bash
# macOS
brew install ffmpeg

# Ubuntu/Debian
sudo apt update && sudo apt install ffmpeg

# Windows - download from https://ffmpeg.org/download.html
```

### 2. Install the Project

```bash
# Clone the repository
git clone <your-repo-url>
cd youtube_content_llm

# Install Python dependencies
pip install -r requirements.txt
```

### 3. Get Your API Keys

You need three API keys. Create a `.env` file in the project root:

```bash
# Required: OpenAI API Key
# Get it from: https://platform.openai.com/api-keys
OPENAI_API_KEY=sk-your-key-here

# Required: YouTube Data API v3 Key
# Get it from: https://console.cloud.google.com/apis/credentials
# Enable "YouTube Data API v3" in your Google Cloud project
YOUTUBE_API_KEY=your-youtube-api-key

# Required: Milvus Vector Database
# Sign up free at: https://cloud.zilliz.com
MILVUS_URI=https://your-instance.zillizcloud.com
MILVUS_TOKEN=your-milvus-token
```

### 4. Run the Chat Interface

To query existing data:

```bash
python main.py
```

Open http://localhost:8000 in your browser.

### 5. Process New Videos

To download and transcribe new videos from YouTube:

```bash
# Process new videos once
python automated_pipeline.py

# See what's been processed
python automated_pipeline.py --stats
```

---

## How It Works

```
You ask a question
       |
       v
Question converted to vector embedding (OpenAI)
       |
       v
Similar segments found in vector database (Milvus)
       |
       v
AI generates answer using those segments (GPT-3.5)
       |
       v
You get an answer + links to source videos
```

When you run the pipeline, it:
1. Fetches video info from YouTube channels (using YouTube Data API)
2. Downloads audio from new videos (using yt-dlp)
3. Transcribes audio to text (using OpenAI Whisper)
4. Breaks transcripts into searchable chunks
5. Stores everything in the vector database

---

## Currently Tracked Channels

The system tracks these music production YouTubers:

- **Zen World** - Arrangement, sound design, tech house and techno tutorials
- **Alice Efe** - Music production tutorials

You can add more channels. See [Adding New Creators](#adding-new-creators) below.

---

## Project Structure

Key files:

```
youtube_content_llm/
├── main.py                    # Web server - run this for the chat interface
├── automated_pipeline.py      # Process new videos - run to update content
├── include/                   # Core modules
│   ├── youtube_transcript_downloader.py  # YouTube API + transcription
│   ├── add_transcripts_to_rag.py         # Upload to vector database
│   └── video_tracker.py                  # Track processed videos
├── templates/index.html       # Chat interface HTML
├── static/                    # CSS and JavaScript
├── .env                       # Your API keys (create this)
└── requirements.txt           # Python dependencies
```

---

## Common Tasks

### Start the Chat Interface

```bash
python main.py
# Opens at http://localhost:8000
```

### Process New Videos

```bash
# Run once
python automated_pipeline.py

# Run continuously (checks every 60 minutes)
python automated_pipeline.py --continuous --interval 60

# View statistics
python automated_pipeline.py --stats
```

### Adding New Creators

Edit `include/youtube_transcript_downloader.py` and add to the `CREATORS` dictionary:

```python
CREATORS = {
    "Zen World": {
        "url": "https://www.youtube.com/@ZenWorld",
        "description": "Tech house and techno tutorials"
    },
    "Your New Creator": {
        "url": "https://www.youtube.com/@ChannelHandle",
        "description": "What they teach"
    }
}
```

Then run `python automated_pipeline.py` to process their videos.

---

## Troubleshooting

### "Sign in to confirm you're not a bot"

This happens when YouTube blocks scraping. The system uses YouTube Data API v3 to avoid this. Make sure your `YOUTUBE_API_KEY` is set correctly in `.env`.

### "OPENAI_API_KEY not found"

Check that your `.env` file exists in the project root and contains your API key.

### "Milvus connection failed"

1. Verify your Zilliz Cloud instance is running at https://cloud.zilliz.com
2. Check that `MILVUS_URI` and `MILVUS_TOKEN` are correct in `.env`

### "ffmpeg not found"

FFmpeg must be installed and in your PATH. See the installation commands in Prerequisites above.

### OpenAI rate limits

If you hit rate limits, reduce the number of videos processed at once by adding to `.env`:
```bash
MAX_VIDEOS_PER_CHECK=3
```

---

## Cost Estimates

| Service | Usage | Monthly Cost |
|---------|-------|--------------|
| OpenAI (Whisper, Embeddings, Chat) | Light usage | $5-15 |
| Zilliz Cloud (Milvus) | Free tier | $0 |
| YouTube Data API | Free tier | $0 |

Typical monthly cost: **$5-15** depending on how many videos you process.

---

## Additional Resources

- [OpenAI API Docs](https://platform.openai.com/docs)
- [YouTube Data API v3](https://developers.google.com/youtube/v3)
- [Milvus Documentation](https://milvus.io/docs)
- [FastAPI Documentation](https://fastapi.tiangolo.com/)

---

## License

MIT
