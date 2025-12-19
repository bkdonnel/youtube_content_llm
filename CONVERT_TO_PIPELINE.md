# Converting to an Automated Data Pipeline

## Table of Contents
1. [Overview](#overview)
2. [Use Case: Music Production Tutorials](#use-case-music-production-tutorials)
3. [Architecture Changes](#architecture-changes)
4. [Implementation Steps](#implementation-steps)
5. [Code Components](#code-components)
6. [Deployment Options](#deployment-options)
7. [Testing & Monitoring](#testing--monitoring)
8. [Troubleshooting](#troubleshooting)

---

## Overview

This guide shows how to convert the YouTube Transcript RAG system from a **manual batch processing** system into a **fully automated data pipeline** that:

- ✅ **Automatically detects** new videos from creators
- ✅ **Downloads and transcribes** new content
- ✅ **Adds to RAG system** without manual intervention
- ✅ **Sends notifications** when new videos are processed
- ✅ **Tracks processing history** to avoid duplicates
- ✅ **Runs continuously** with configurable intervals

### What Changes?

**Before (Manual)**:
```bash
# Step 1: Manually run downloader
python youtube_transcript_downloader.py

# Step 2: Manually integrate to RAG
python add_transcripts_to_rag.py
```

**After (Automated)**:
```bash
# Single command runs continuously
python automated_pipeline.py --continuous --interval 60

# Or schedule with cron/systemd
```

---

## Use Case: Music Production Tutorials

Let's say you want to:
- Extract transcripts from music production tutorial channels
- Search for specific techniques (e.g., "How to sidechain compress?")
- Get automatic updates when new tutorials are uploaded
- Build a searchable knowledge base of production tips

**Example Creators**:
- In The Mix (FL Studio tutorials)
- Busy Works Beats (Music production)
- Simon Servida (Ableton Live)
- Reid Stefan (Logic Pro)
- Andrew Huang (Creative production)

---

## Architecture Changes

### Original Architecture

```
┌──────────────┐      ┌──────────────┐      ┌──────────────┐
│   Manual     │      │   Manual     │      │   Manual     │
│   Download   │─────>│   Integrate  │─────>│   Query      │
│              │      │   to RAG     │      │              │
└──────────────┘      └──────────────┘      └──────────────┘
```

### New Automated Pipeline Architecture

```
┌─────────────────────────────────────────────────────────────┐
│              AUTOMATED MUSIC PRODUCTION PIPELINE             │
└─────────────────────────────────────────────────────────────┘

┌──────────────────┐      ┌──────────────────┐      ┌──────────────┐
│   SCHEDULER      │      │   PROCESSOR      │      │  NOTIFIER    │
│  (Check new      │─────>│  (Download &     │─────>│  (Alert on   │
│   videos)        │      │   Transcribe)    │      │   new videos)│
└──────────────────┘      └──────────────────┘      └──────────────┘
        │                          │                        │
        ▼                          ▼                        ▼
┌──────────────────┐      ┌──────────────────┐      ┌──────────────┐
│ Video Tracker    │      │  RAG Integration │      │  Log/Email   │
│ (SQLite DB)      │      │  (Auto-add)      │      │  /Webhook    │
└──────────────────┘      └──────────────────┘      └──────────────┘

COMPONENTS:

1. Video Tracker (SQLite Database)
   - Stores processed video IDs
   - Prevents duplicate processing
   - Tracks errors and statistics

2. Scheduler
   - Checks for new videos at intervals
   - Compares against tracker database
   - Triggers processing for new content

3. Processor
   - Downloads audio (yt-dlp)
   - Generates transcripts (Whisper)
   - Adds to RAG system (FastAPI)

4. Notifier
   - Sends alerts via Slack/Discord/Email
   - Reports errors and summaries
```

### Data Flow

```
┌─────────────────────────────────────────────────────────────┐
│ AUTOMATED PIPELINE DATA FLOW                                 │
└─────────────────────────────────────────────────────────────┘

Every N Minutes (configurable):

1. SCHEDULER WAKES UP
   ├─> Check YouTube for latest videos from each creator
   ├─> Query tracker DB for processed video IDs
   └─> Identify NEW videos (not in DB)

2. FOR EACH NEW VIDEO:
   ├─> Download audio (m4a format)
   ├─> Split if > 25 minutes (ffmpeg)
   ├─> Transcribe with Whisper API
   ├─> Save JSON + TXT files
   ├─> INSERT into tracker DB (status: "processing")
   └─> Clean up audio files

3. RAG INTEGRATION:
   ├─> Break transcript into segments
   ├─> Generate embeddings (OpenAI)
   ├─> Insert into Milvus vector DB
   └─> UPDATE tracker DB (rag_integrated: TRUE)

4. NOTIFICATION:
   ├─> Send alert about new video
   ├─> Include video title, creator, URL
   └─> Log to file

5. ERROR HANDLING:
   ├─> Catch any exceptions
   ├─> Log to tracker DB (processing_errors table)
   ├─> Send error notification
   └─> Continue with next video

6. SLEEP:
   └─> Wait N minutes before next check
```

---

## Implementation Steps

### Step 1: Update Creator Configuration

**File**: Create `automated_pipeline.py` (or modify existing downloader)

Replace generic creators with music production channels:

```python
# At the top of automated_pipeline.py

CREATORS = {
    "In The Mix": {
        "url": "https://www.youtube.com/@inthemix",
        "description": "FL Studio tutorials and music production tips"
    },
    "Busy Works Beats": {
        "url": "https://www.youtube.com/@BusyWorksBeats",
        "description": "Music production tutorials for beginners"
    },
    "Simon Servida": {
        "url": "https://www.youtube.com/@SimonServida",
        "description": "Ableton Live and production techniques"
    },
    "Reid Stefan": {
        "url": "https://www.youtube.com/@ReidStefan",
        "description": "Logic Pro and mixing tutorials"
    },
    "Andrew Huang": {
        "url": "https://www.youtube.com/@andrewhuang",
        "description": "Creative music production and sound design"
    },
    "You Suck at Producing": {
        "url": "https://www.youtube.com/@UnderbridgeProductions",
        "description": "Ableton and electronic music production"
    },
    "Venus Theory": {
        "url": "https://www.youtube.com/@VenusTheory",
        "description": "Synthesis and sound design"
    },
    # Add your favorite music production channels here
}

# Configuration
CHECK_INTERVAL_MINUTES = 60  # Check every hour
MAX_VIDEOS_PER_CHECK = 5     # Check latest 5 videos
OUTPUT_DIR = "music_tutorials"
```

---

### Step 2: Create Video Tracking Database

**File**: Create `video_tracker.py`

This SQLite database tracks which videos have been processed to avoid duplicates.

**Database Schema**:

```sql
-- Table 1: Track processed videos
CREATE TABLE processed_videos (
    video_id TEXT PRIMARY KEY,           -- YouTube video ID
    channel_name TEXT NOT NULL,          -- Creator name
    video_title TEXT NOT NULL,           -- Video title
    upload_date TEXT,                    -- Upload date (YYYYMMDD)
    processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    transcript_path TEXT,                -- Path to JSON transcript
    rag_integrated BOOLEAN DEFAULT 0,    -- Added to RAG?
    status TEXT DEFAULT 'completed'      -- completed, failed, processing
);

-- Table 2: Track channel check times
CREATE TABLE channel_checks (
    channel_name TEXT PRIMARY KEY,
    last_checked TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    last_video_id TEXT                   -- Most recent video ID
);

-- Table 3: Track errors
CREATE TABLE processing_errors (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    video_id TEXT,
    channel_name TEXT,
    error_message TEXT,
    occurred_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
```

**Key Methods**:

```python
class VideoTracker:
    def is_video_processed(self, video_id: str) -> bool
        """Check if video already processed."""

    def mark_video_processed(self, video_id, channel_name, ...)
        """Add video to database."""

    def mark_rag_integrated(self, video_id: str)
        """Mark as added to RAG."""

    def get_unintegrated_videos(self) -> List[Dict]
        """Get videos not yet in RAG."""

    def log_error(self, video_id, channel_name, error)
        """Log processing errors."""

    def get_stats(self) -> Dict
        """Get processing statistics."""
```

See full implementation in the [Code Components](#code-components) section below.

---

### Step 3: Create Automated Pipeline Script

**File**: Create `automated_pipeline.py`

This is the main automation script that orchestrates everything.

**Key Components**:

```python
class MusicProductionPipeline:
    def __init__(self, output_dir, rag_api_url, max_videos_per_check):
        self.tracker = VideoTracker()
        self.downloader = YouTubeTranscriptDownloader(...)
        self.rag_integrator = TranscriptRAGIntegrator(...)

    def get_new_videos(self, creator_name, creator_url):
        """Check for new videos not in tracker DB."""
        # 1. Fetch latest videos from YouTube
        # 2. Compare against tracker DB
        # 3. Return list of new videos

    async def process_new_video(self, video_info):
        """Download, transcribe, and add to RAG."""
        # 1. Download audio
        # 2. Generate transcript with Whisper
        # 3. Save to files
        # 4. Add to tracker DB
        # 5. Integrate to RAG system
        # 6. Update tracker as integrated

    async def check_and_process_all_creators(self):
        """Main pipeline run - check all creators."""
        # For each creator:
        #   - Get new videos
        #   - Process each new video
        #   - Print summary

    async def run_continuous(self, check_interval_minutes):
        """Run pipeline continuously at intervals."""
        while True:
            await self.check_and_process_all_creators()
            await asyncio.sleep(check_interval_minutes * 60)
```

**Command-line Interface**:

```bash
# Run once (check and process new videos)
python automated_pipeline.py

# Run continuously (check every 60 minutes)
python automated_pipeline.py --continuous --interval 60

# Custom check interval (every 30 minutes)
python automated_pipeline.py --continuous --interval 30

# Custom output directory
python automated_pipeline.py --output-dir "my_tutorials"

# Show statistics only
python automated_pipeline.py --stats
```

See full implementation in the [Code Components](#code-components) section below.

---

### Step 4: Add Notification System (Optional)

**File**: Create `notifications.py`

Send alerts when new videos are processed or errors occur.

**Supported Channels**:
- Slack (via webhook)
- Discord (via webhook)
- Email (via SMTP)
- Custom webhook (generic HTTP POST)

**Key Methods**:

```python
class NotificationManager:
    def notify_new_video(self, video_info):
        """Alert when new video is processed."""

    def notify_error(self, error_info):
        """Alert on processing errors."""

    def notify_summary(self, summary):
        """Send daily/weekly summary."""
```

**Environment Variables** (`.env`):

```bash
# Slack
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK/URL

# Discord
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR/WEBHOOK

# Email (Gmail example)
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SENDER_EMAIL=your-email@gmail.com
SENDER_PASSWORD=your-app-password
RECIPIENT_EMAIL=notify@example.com
```

See full implementation in the [Code Components](#code-components) section below.

---

### Step 5: Update Environment Variables

**File**: `.env`

Add notification settings and any pipeline-specific configuration:

```bash
# Existing variables
OPENAI_API_KEY=sk-your-openai-api-key
MILVUS_URI=https://your-milvus-instance.cloud.zilliz.com
MILVUS_TOKEN=your-milvus-token

# Pipeline configuration
CHECK_INTERVAL_MINUTES=60
MAX_VIDEOS_PER_CHECK=5
OUTPUT_DIR=music_tutorials

# Notification settings (optional)
SLACK_WEBHOOK_URL=https://hooks.slack.com/services/YOUR/WEBHOOK
DISCORD_WEBHOOK_URL=https://discord.com/api/webhooks/YOUR/WEBHOOK
SMTP_SERVER=smtp.gmail.com
SMTP_PORT=587
SENDER_EMAIL=your-email@gmail.com
SENDER_PASSWORD=your-app-password
RECIPIENT_EMAIL=notify@example.com

# Error handling
MAX_RETRIES=3
RETRY_DELAY_SECONDS=60
```

---

### Step 6: Choose Deployment Method

You have several options for running the pipeline continuously:

#### Option A: Manual Background Process

**Linux/Mac**:
```bash
# Using nohup
nohup python automated_pipeline.py --continuous --interval 60 > pipeline.log 2>&1 &

# Using screen (recommended)
screen -S music-pipeline
python automated_pipeline.py --continuous --interval 60
# Press Ctrl+A then D to detach
# screen -r music-pipeline to reattach

# Using tmux
tmux new -s music-pipeline
python automated_pipeline.py --continuous --interval 60
# Press Ctrl+B then D to detach
# tmux attach -t music-pipeline to reattach
```

**Windows**:
```bash
# Using start
start /B python automated_pipeline.py --continuous --interval 60 > pipeline.log 2>&1
```

#### Option B: Cron Job (Linux/Mac)

**For periodic execution** (not continuous):

```bash
# Edit crontab
crontab -e

# Check every hour (at minute 0)
0 * * * * cd /path/to/project && /path/to/venv/bin/python automated_pipeline.py >> /var/log/pipeline.log 2>&1

# Check every 30 minutes
*/30 * * * * cd /path/to/project && /path/to/venv/bin/python automated_pipeline.py >> /var/log/pipeline.log 2>&1

# Check twice daily (6 AM and 6 PM)
0 6,18 * * * cd /path/to/project && /path/to/venv/bin/python automated_pipeline.py >> /var/log/pipeline.log 2>&1

# Check every Monday at 9 AM
0 9 * * 1 cd /path/to/project && /path/to/venv/bin/python automated_pipeline.py >> /var/log/pipeline.log 2>&1
```

**Cron syntax reference**:
```
* * * * * command
│ │ │ │ │
│ │ │ │ └─── Day of week (0-7, Sunday = 0 or 7)
│ │ │ └───── Month (1-12)
│ │ └─────── Day of month (1-31)
│ └───────── Hour (0-23)
└─────────── Minute (0-59)
```

#### Option C: Systemd Service (Linux - Recommended for Production)

**Create service file**: `/etc/systemd/system/music-pipeline.service`

```ini
[Unit]
Description=Music Production Tutorial Pipeline
After=network.target

[Service]
Type=simple
User=your_username
Group=your_group
WorkingDirectory=/path/to/fastapi-vibe-coding
Environment="PATH=/path/to/venv/bin:/usr/local/bin:/usr/bin"
Environment="PYTHONUNBUFFERED=1"
ExecStart=/path/to/venv/bin/python automated_pipeline.py --continuous --interval 60
Restart=always
RestartSec=10
StandardOutput=append:/var/log/music-pipeline.log
StandardError=append:/var/log/music-pipeline.error.log

[Install]
WantedBy=multi-user.target
```

**Enable and manage service**:

```bash
# Reload systemd configuration
sudo systemctl daemon-reload

# Enable service (start on boot)
sudo systemctl enable music-pipeline

# Start service
sudo systemctl start music-pipeline

# Check status
sudo systemctl status music-pipeline

# View logs (live)
sudo journalctl -u music-pipeline -f

# View logs (last 100 lines)
sudo journalctl -u music-pipeline -n 100

# Stop service
sudo systemctl stop music-pipeline

# Restart service
sudo systemctl restart music-pipeline

# Disable service (don't start on boot)
sudo systemctl disable music-pipeline
```

#### Option D: Docker Container (Cross-Platform - Recommended)

**Create Dockerfile**:

```dockerfile
FROM python:3.10-slim

# Install system dependencies
RUN apt-get update && \
    apt-get install -y ffmpeg && \
    rm -rf /var/lib/apt/lists/*

# Set working directory
WORKDIR /app

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application files
COPY . .

# Create directories
RUN mkdir -p music_tutorials logs

# Run the pipeline
CMD ["python", "automated_pipeline.py", "--continuous", "--interval", "60"]
```

**Create docker-compose.yml**:

```yaml
version: '3.8'

services:
  pipeline:
    build: .
    container_name: music-pipeline
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - MILVUS_URI=${MILVUS_URI}
      - MILVUS_TOKEN=${MILVUS_TOKEN}
      - SLACK_WEBHOOK_URL=${SLACK_WEBHOOK_URL}
    volumes:
      - ./music_tutorials:/app/music_tutorials
      - ./video_tracker.db:/app/video_tracker.db
      - ./logs:/app/logs
    restart: unless-stopped
    networks:
      - pipeline-network

  # Optional: Run FastAPI server in same compose
  fastapi:
    build: .
    container_name: rag-api
    command: python main.py
    ports:
      - "8000:8000"
    environment:
      - OPENAI_API_KEY=${OPENAI_API_KEY}
      - MILVUS_URI=${MILVUS_URI}
      - MILVUS_TOKEN=${MILVUS_TOKEN}
    restart: unless-stopped
    networks:
      - pipeline-network

networks:
  pipeline-network:
    driver: bridge
```

**Docker commands**:

```bash
# Build and start
docker-compose up -d

# View logs
docker-compose logs -f pipeline

# View logs (last 100 lines)
docker-compose logs --tail=100 pipeline

# Stop
docker-compose down

# Restart
docker-compose restart pipeline

# Rebuild after code changes
docker-compose up -d --build

# Execute commands inside container
docker-compose exec pipeline python automated_pipeline.py --stats

# Access container shell
docker-compose exec pipeline /bin/bash
```

#### Option E: Kubernetes (Production at Scale)

**Create deployment.yaml**:

```yaml
apiVersion: apps/v1
kind: Deployment
metadata:
  name: music-pipeline
spec:
  replicas: 1
  selector:
    matchLabels:
      app: music-pipeline
  template:
    metadata:
      labels:
        app: music-pipeline
    spec:
      containers:
      - name: pipeline
        image: your-registry/music-pipeline:latest
        env:
        - name: OPENAI_API_KEY
          valueFrom:
            secretKeyRef:
              name: pipeline-secrets
              key: openai-api-key
        - name: MILVUS_URI
          valueFrom:
            secretKeyRef:
              name: pipeline-secrets
              key: milvus-uri
        volumeMounts:
        - name: data
          mountPath: /app/music_tutorials
        - name: db
          mountPath: /app/video_tracker.db
      volumes:
      - name: data
        persistentVolumeClaim:
          claimName: pipeline-data-pvc
      - name: db
        persistentVolumeClaim:
          claimName: pipeline-db-pvc
```

---

### Step 7: Setup Logging

**Create logging configuration** in `automated_pipeline.py`:

```python
import logging
from logging.handlers import RotatingFileHandler

# Configure logging
def setup_logging(log_file: str = "pipeline.log"):
    """Setup logging configuration."""

    # Create logger
    logger = logging.getLogger("MusicPipeline")
    logger.setLevel(logging.INFO)

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(logging.INFO)
    console_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    console_handler.setFormatter(console_format)

    # File handler (rotate at 10MB, keep 5 backups)
    file_handler = RotatingFileHandler(
        log_file,
        maxBytes=10*1024*1024,  # 10 MB
        backupCount=5
    )
    file_handler.setLevel(logging.INFO)
    file_format = logging.Formatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    file_handler.setFormatter(file_format)

    # Add handlers
    logger.addHandler(console_handler)
    logger.addHandler(file_handler)

    return logger

# Usage
logger = setup_logging("logs/pipeline.log")
logger.info("Pipeline started")
logger.error("Error processing video", exc_info=True)
```

---

### Step 8: Testing

**Test the pipeline before production deployment**:

```bash
# Test 1: Verify tracker database
python -c "from video_tracker import VideoTracker; t = VideoTracker(); print(t.get_stats())"

# Test 2: Check for new videos (dry run)
python automated_pipeline.py --stats

# Test 3: Process one creator only
# (Modify script to accept --creator argument)
python automated_pipeline.py --creator "In The Mix"

# Test 4: Run once (not continuous)
python automated_pipeline.py

# Test 5: Run continuously with short interval (5 minutes)
python automated_pipeline.py --continuous --interval 5

# Test 6: Test notification system
python -c "from notifications import NotificationManager; n = NotificationManager(); n.notify_new_video({'title': 'Test', 'creator': 'Test', 'id': 'test123', 'url': 'https://youtube.com/watch?v=test'})"

# Test 7: Check logs
tail -f pipeline.log

# Test 8: Verify RAG integration
# Open browser to http://localhost:8000
# Query: "What topics are covered in the latest videos?"
```

---

## Code Components

### Full Implementation: video_tracker.py

```python
#!/usr/bin/env python3
"""
Video Tracker Database
Tracks processed videos to avoid duplicates and manage pipeline state
"""

import sqlite3
from pathlib import Path
from typing import List, Dict, Optional
from datetime import datetime


class VideoTracker:
    """Track processed videos and pipeline state using SQLite."""

    def __init__(self, db_path: str = "video_tracker.db"):
        """Initialize video tracker with SQLite database."""
        self.db_path = Path(db_path)
        self.conn = None
        self.init_database()

    def init_database(self):
        """Create database tables if they don't exist."""
        self.conn = sqlite3.connect(self.db_path)
        cursor = self.conn.cursor()

        # Table to track processed videos
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS processed_videos (
                video_id TEXT PRIMARY KEY,
                channel_name TEXT NOT NULL,
                video_title TEXT NOT NULL,
                upload_date TEXT,
                processed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                transcript_path TEXT,
                rag_integrated BOOLEAN DEFAULT 0,
                status TEXT DEFAULT 'completed'
            )
        """)

        # Table to track last check time for each channel
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS channel_checks (
                channel_name TEXT PRIMARY KEY,
                last_checked TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                last_video_id TEXT
            )
        """)

        # Table to track processing errors
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS processing_errors (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                video_id TEXT,
                channel_name TEXT,
                error_message TEXT,
                occurred_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        self.conn.commit()

    def is_video_processed(self, video_id: str) -> bool:
        """Check if a video has already been processed."""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM processed_videos WHERE video_id = ?",
            (video_id,)
        )
        count = cursor.fetchone()[0]
        return count > 0

    def mark_video_processed(
        self,
        video_id: str,
        channel_name: str,
        video_title: str,
        upload_date: str,
        transcript_path: str,
        rag_integrated: bool = False
    ):
        """Mark a video as processed."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO processed_videos
            (video_id, channel_name, video_title, upload_date, transcript_path, rag_integrated)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (video_id, channel_name, video_title, upload_date, transcript_path, rag_integrated))
        self.conn.commit()

    def mark_rag_integrated(self, video_id: str):
        """Mark a video as integrated into RAG system."""
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE processed_videos SET rag_integrated = 1 WHERE video_id = ?",
            (video_id,)
        )
        self.conn.commit()

    def get_unintegrated_videos(self) -> List[Dict]:
        """Get videos that have been transcribed but not added to RAG."""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT video_id, channel_name, video_title, transcript_path
            FROM processed_videos
            WHERE rag_integrated = 0
        """)

        results = cursor.fetchall()
        return [
            {
                'video_id': row[0],
                'channel_name': row[1],
                'video_title': row[2],
                'transcript_path': row[3]
            }
            for row in results
        ]

    def log_error(self, video_id: str, channel_name: str, error_message: str):
        """Log a processing error."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO processing_errors (video_id, channel_name, error_message)
            VALUES (?, ?, ?)
        """, (video_id, channel_name, error_message))
        self.conn.commit()

    def update_channel_check(self, channel_name: str, last_video_id: Optional[str] = None):
        """Update the last check time for a channel."""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT OR REPLACE INTO channel_checks (channel_name, last_checked, last_video_id)
            VALUES (?, CURRENT_TIMESTAMP, ?)
        """, (channel_name, last_video_id))
        self.conn.commit()

    def get_stats(self) -> Dict:
        """Get processing statistics."""
        cursor = self.conn.cursor()

        # Total processed videos
        cursor.execute("SELECT COUNT(*) FROM processed_videos")
        total_processed = cursor.fetchone()[0]

        # RAG integrated videos
        cursor.execute("SELECT COUNT(*) FROM processed_videos WHERE rag_integrated = 1")
        rag_integrated = cursor.fetchone()[0]

        # Videos by channel
        cursor.execute("""
            SELECT channel_name, COUNT(*) as count
            FROM processed_videos
            GROUP BY channel_name
        """)
        by_channel = {row[0]: row[1] for row in cursor.fetchall()}

        # Recent errors
        cursor.execute("""
            SELECT COUNT(*) FROM processing_errors
            WHERE occurred_at > datetime('now', '-24 hours')
        """)
        recent_errors = cursor.fetchone()[0]

        return {
            'total_processed': total_processed,
            'rag_integrated': rag_integrated,
            'pending_integration': total_processed - rag_integrated,
            'by_channel': by_channel,
            'recent_errors': recent_errors
        }

    def close(self):
        """Close database connection."""
        if self.conn:
            self.conn.close()


# Example usage
if __name__ == "__main__":
    tracker = VideoTracker()

    # Get statistics
    stats = tracker.get_stats()
    print("📊 Pipeline Statistics:")
    print(f"   Total processed: {stats['total_processed']}")
    print(f"   RAG integrated: {stats['rag_integrated']}")
    print(f"   Pending: {stats['pending_integration']}")
    print(f"   Recent errors: {stats['recent_errors']}")

    if stats['by_channel']:
        print("\n📺 By Channel:")
        for channel, count in stats['by_channel'].items():
            print(f"   {channel}: {count} videos")

    tracker.close()
```

### Full Implementation: notifications.py

```python
#!/usr/bin/env python3
"""
Notification System
Send alerts via email, Slack, Discord, or webhook
"""

import os
import requests
from typing import Dict, Optional
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime


class NotificationManager:
    """Manage notifications across multiple channels."""

    def __init__(self):
        """Initialize notification manager with credentials from environment."""
        self.slack_webhook = os.getenv("SLACK_WEBHOOK_URL")
        self.discord_webhook = os.getenv("DISCORD_WEBHOOK_URL")
        self.email_config = {
            'smtp_server': os.getenv("SMTP_SERVER"),
            'smtp_port': int(os.getenv("SMTP_PORT", "587")),
            'sender_email': os.getenv("SENDER_EMAIL"),
            'sender_password': os.getenv("SENDER_PASSWORD"),
            'recipient_email': os.getenv("RECIPIENT_EMAIL")
        }

    def notify_new_video(self, video_info: Dict):
        """Send notification about a new video being processed."""
        title = f"🎬 New Video Processed"
        message = f"""
New music production tutorial added to database:

Creator: {video_info.get('creator', 'Unknown')}
Title: {video_info.get('title', 'Unknown')}
Video ID: {video_info.get('id', 'Unknown')}
URL: {video_info.get('url', 'N/A')}
Duration: {video_info.get('duration', 0) / 60:.1f} minutes
Processed: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

You can now search for content from this video in the RAG system!
"""

        self._send_notification(title, message)

    def notify_error(self, error_info: Dict):
        """Send notification about a processing error."""
        title = f"❌ Pipeline Error"
        message = f"""
Error occurred during video processing:

Creator: {error_info.get('creator', 'Unknown')}
Video: {error_info.get('video_title', 'Unknown')}
Video ID: {error_info.get('video_id', 'Unknown')}
Error: {error_info.get('error', 'Unknown error')}
Occurred: {error_info.get('occurred_at', datetime.now().strftime('%Y-%m-%d %H:%M:%S'))}

Please check the logs for more details.
"""

        self._send_notification(title, message)

    def notify_summary(self, summary: Dict):
        """Send daily/weekly summary notification."""
        title = f"📊 Pipeline Summary Report"
        message = f"""
Pipeline Summary Report
Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

New videos processed: {summary.get('new_videos', 0)}
Total in database: {summary.get('total_videos', 0)}
RAG integrated: {summary.get('rag_integrated', 0)}
Pending integration: {summary.get('pending', 0)}
Errors: {summary.get('errors', 0)}

By Creator:
{self._format_creator_stats(summary.get('by_creator', {}))}
"""

        self._send_notification(title, message)

    def _send_notification(self, title: str, message: str):
        """Send notification via all configured channels."""
        if self.slack_webhook:
            self._send_slack(title, message)

        if self.discord_webhook:
            self._send_discord(title, message)

        if all(self.email_config.values()):
            self._send_email(title, message)

    def _send_slack(self, title: str, message: str):
        """Send Slack notification."""
        try:
            payload = {
                "text": f"*{title}*\n```{message}```"
            }
            response = requests.post(
                self.slack_webhook,
                json=payload,
                timeout=10
            )
            response.raise_for_status()
            print(f"✅ Slack notification sent: {title}")
        except Exception as e:
            print(f"⚠️  Failed to send Slack notification: {e}")

    def _send_discord(self, title: str, message: str):
        """Send Discord notification."""
        try:
            payload = {
                "content": f"**{title}**\n```{message}```"
            }
            response = requests.post(
                self.discord_webhook,
                json=payload,
                timeout=10
            )
            response.raise_for_status()
            print(f"✅ Discord notification sent: {title}")
        except Exception as e:
            print(f"⚠️  Failed to send Discord notification: {e}")

    def _send_email(self, title: str, message: str):
        """Send email notification."""
        try:
            msg = MIMEMultipart()
            msg['From'] = self.email_config['sender_email']
            msg['To'] = self.email_config['recipient_email']
            msg['Subject'] = title

            msg.attach(MIMEText(message, 'plain'))

            with smtplib.SMTP(
                self.email_config['smtp_server'],
                self.email_config['smtp_port']
            ) as server:
                server.starttls()
                server.login(
                    self.email_config['sender_email'],
                    self.email_config['sender_password']
                )
                server.send_message(msg)

            print(f"✅ Email notification sent: {title}")
        except Exception as e:
            print(f"⚠️  Failed to send email notification: {e}")

    def _format_creator_stats(self, by_creator: Dict) -> str:
        """Format creator statistics for notification."""
        if not by_creator:
            return "  (No data)"

        lines = []
        for creator, count in by_creator.items():
            lines.append(f"  • {creator}: {count} videos")
        return "\n".join(lines)


# Example usage
if __name__ == "__main__":
    from dotenv import load_dotenv
    load_dotenv()

    notifier = NotificationManager()

    # Test new video notification
    notifier.notify_new_video({
        'creator': 'In The Mix',
        'title': 'How to Sidechain in FL Studio',
        'id': 'test123',
        'url': 'https://youtube.com/watch?v=test123',
        'duration': 720
    })

    # Test error notification
    notifier.notify_error({
        'creator': 'Busy Works Beats',
        'video_title': 'Making Beats Tutorial',
        'video_id': 'test456',
        'error': 'Whisper API timeout',
        'occurred_at': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    })
```

---

## Deployment Options

### Comparison Table

| Method | Pros | Cons | Best For |
|--------|------|------|----------|
| **Manual (nohup/screen)** | Simple, no setup | Not persistent, manual restart | Development, testing |
| **Cron** | Simple, built-in | Not for continuous runs | Periodic checks (hourly/daily) |
| **Systemd** | Auto-restart, logging, boot start | Linux only, requires sudo | Production Linux servers |
| **Docker** | Portable, isolated, easy deploy | Requires Docker | Cross-platform, cloud deployment |
| **Kubernetes** | Scalable, fault-tolerant | Complex setup | Large-scale production |

### Recommended Setup by Scale

**Small Scale (1-10 creators)**:
- Cron job or systemd service
- Check every 1-2 hours
- Single server

**Medium Scale (10-50 creators)**:
- Docker container
- Check every 30-60 minutes
- Could use multiple containers for parallel processing

**Large Scale (50+ creators)**:
- Kubernetes deployment
- Check every 15-30 minutes
- Distributed processing with worker pods
- Message queue (RabbitMQ/Celery) for task distribution

---

## Testing & Monitoring

### Pre-Production Checklist

```bash
# 1. Test video tracker database
python -c "from video_tracker import VideoTracker; t = VideoTracker(); print(t.get_stats())"

# 2. Test notification system
python -c "from notifications import NotificationManager; n = NotificationManager(); n.notify_new_video({'title': 'Test', 'creator': 'Test', 'id': 'test', 'url': 'https://youtube.com/watch?v=test', 'duration': 300})"

# 3. Verify environment variables
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print('OPENAI_API_KEY:', 'SET' if os.getenv('OPENAI_API_KEY') else 'NOT SET')"

# 4. Test single creator (dry run)
python automated_pipeline.py --creator "In The Mix" --max-videos 1

# 5. Test continuous mode (short interval)
python automated_pipeline.py --continuous --interval 5

# 6. Check logs
tail -f pipeline.log

# 7. Verify RAG integration
# Query via web interface: http://localhost:8000
```

### Monitoring in Production

**Log Monitoring**:
```bash
# Real-time log monitoring
tail -f logs/pipeline.log

# Search for errors
grep "ERROR" logs/pipeline.log

# Count processed videos today
grep "Successfully processed" logs/pipeline.log | grep "$(date +%Y-%m-%d)" | wc -l

# Check recent errors
tail -100 logs/pipeline.log | grep "ERROR"
```

**Database Monitoring**:
```bash
# Get statistics
python automated_pipeline.py --stats

# Query database directly
sqlite3 video_tracker.db "SELECT COUNT(*) FROM processed_videos WHERE processed_at > datetime('now', '-24 hours');"

# Check unintegrated videos
sqlite3 video_tracker.db "SELECT * FROM processed_videos WHERE rag_integrated = 0;"

# Recent errors
sqlite3 video_tracker.db "SELECT * FROM processing_errors ORDER BY occurred_at DESC LIMIT 10;"
```

**Health Checks**:
```python
# health_check.py
from video_tracker import VideoTracker
from notifications import NotificationManager
import requests
import sys

def check_rag_api():
    """Check if RAG API is running."""
    try:
        response = requests.get("http://localhost:8000/api/health", timeout=5)
        return response.status_code == 200
    except:
        return False

def check_database():
    """Check if database is accessible."""
    try:
        tracker = VideoTracker()
        stats = tracker.get_stats()
        tracker.close()
        return True
    except:
        return False

def main():
    issues = []

    if not check_rag_api():
        issues.append("RAG API is not accessible")

    if not check_database():
        issues.append("Database is not accessible")

    if issues:
        # Send alert
        notifier = NotificationManager()
        notifier.notify_error({
            'creator': 'System',
            'video_title': 'Health Check',
            'video_id': 'N/A',
            'error': '; '.join(issues),
            'occurred_at': 'Now'
        })
        sys.exit(1)
    else:
        print("✅ All systems operational")
        sys.exit(0)

if __name__ == "__main__":
    main()
```

**Add to crontab** for hourly health checks:
```bash
0 * * * * cd /path/to/project && /path/to/venv/bin/python health_check.py
```

---

## Troubleshooting

### Common Issues

**1. "OPENAI_API_KEY not found"**
```bash
# Check .env file
cat .env | grep OPENAI_API_KEY

# Verify it's loaded
python -c "import os; from dotenv import load_dotenv; load_dotenv(); print(os.getenv('OPENAI_API_KEY'))"

# Solution: Add to .env
echo "OPENAI_API_KEY=sk-your-key-here" >> .env
```

**2. "Database is locked"**
```bash
# Check if another process is using the database
lsof video_tracker.db

# Solution: Close other connections or restart pipeline
```

**3. "YouTube video not accessible"**
```bash
# Test with yt-dlp directly
yt-dlp --list-formats "https://youtube.com/watch?v=VIDEO_ID"

# Update yt-dlp
pip install --upgrade yt-dlp

# Check if video is age-restricted or private
```

**4. "Whisper API timeout"**
```bash
# Check file size
ls -lh creator_videos/Creator/Video.m4a

# Solution: Automatic splitting should handle this
# If not, adjust chunk duration:
python add_transcripts_to_rag.py --chunk-duration 20
```

**5. "Milvus connection failed"**
```bash
# Test connection
python -c "from pymilvus import MilvusClient; c = MilvusClient(uri='YOUR_URI', token='YOUR_TOKEN'); print(c.list_collections())"

# Check credentials in .env
cat .env | grep MILVUS
```

**6. "Pipeline stops unexpectedly"**
```bash
# Check logs for errors
tail -100 logs/pipeline.log | grep ERROR

# Check system resources
df -h  # Disk space
free -h  # Memory
top  # CPU usage

# Restart with logging
python automated_pipeline.py --continuous --interval 60 2>&1 | tee pipeline.log
```

**7. "Notifications not sending"**
```bash
# Test Slack webhook
curl -X POST YOUR_SLACK_WEBHOOK -H 'Content-Type: application/json' -d '{"text": "Test"}'

# Test Discord webhook
curl -X POST YOUR_DISCORD_WEBHOOK -H 'Content-Type: application/json' -d '{"content": "Test"}'

# Test email credentials
python -c "from notifications import NotificationManager; n = NotificationManager(); print(n.email_config)"
```

### Debug Mode

Add verbose logging to `automated_pipeline.py`:

```python
import logging

# Set to DEBUG level
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("debug.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

# In your code:
logger.debug(f"Checking creator: {creator_name}")
logger.debug(f"Found videos: {len(videos)}")
logger.debug(f"Video info: {video_info}")
```

Run in debug mode:
```bash
python automated_pipeline.py --continuous --interval 60 2>&1 | tee debug.log
```

---

## Performance Optimization

### Parallel Processing

Process multiple creators concurrently:

```python
import asyncio

async def process_all_creators_parallel(self):
    """Process multiple creators in parallel."""
    tasks = []

    for creator_name, creator_info in CREATORS.items():
        task = self.process_creator_async(creator_name, creator_info)
        tasks.append(task)

    results = await asyncio.gather(*tasks, return_exceptions=True)
    return results

async def process_creator_async(self, creator_name, creator_info):
    """Process one creator asynchronously."""
    new_videos = self.get_new_videos(creator_name, creator_info['url'])

    for video in new_videos:
        await self.process_new_video(video)
```

### Rate Limiting

Avoid hitting API rate limits:

```python
import asyncio
from datetime import datetime, timedelta

class RateLimiter:
    """Simple rate limiter for API calls."""

    def __init__(self, max_calls: int, period_seconds: int):
        self.max_calls = max_calls
        self.period_seconds = period_seconds
        self.calls = []

    async def acquire(self):
        """Wait if necessary to respect rate limit."""
        now = datetime.now()

        # Remove old calls outside the time window
        self.calls = [
            call_time for call_time in self.calls
            if now - call_time < timedelta(seconds=self.period_seconds)
        ]

        # Wait if we've hit the limit
        if len(self.calls) >= self.max_calls:
            oldest_call = min(self.calls)
            sleep_time = (oldest_call + timedelta(seconds=self.period_seconds) - now).total_seconds()
            if sleep_time > 0:
                await asyncio.sleep(sleep_time)

        self.calls.append(now)

# Usage
whisper_limiter = RateLimiter(max_calls=50, period_seconds=60)  # 50 calls per minute

async def transcribe_with_rate_limit(audio_file):
    await whisper_limiter.acquire()
    return await openai.Audio.atranscribe(...)
```

### Caching

Cache embeddings to avoid regeneration:

```python
import pickle
from pathlib import Path

class EmbeddingCache:
    """Cache embeddings to disk."""

    def __init__(self, cache_file: str = "embedding_cache.pkl"):
        self.cache_file = Path(cache_file)
        self.cache = self._load_cache()

    def _load_cache(self):
        if self.cache_file.exists():
            with open(self.cache_file, 'rb') as f:
                return pickle.load(f)
        return {}

    def _save_cache(self):
        with open(self.cache_file, 'wb') as f:
            pickle.dump(self.cache, f)

    def get(self, text: str):
        return self.cache.get(text)

    def set(self, text: str, embedding: list):
        self.cache[text] = embedding
        self._save_cache()

# Usage
cache = EmbeddingCache()

def get_embedding_with_cache(text):
    cached = cache.get(text)
    if cached:
        return cached

    embedding = openai.Embedding.create(input=text)['data'][0]['embedding']
    cache.set(text, embedding)
    return embedding
```

---

## Cost Optimization

### Estimated Costs (100 videos/month)

**OpenAI API**:
- Whisper: 100 videos × 30 min avg × $0.006/min = **$18/month**
- Embeddings: 100 videos × 5000 tokens × $0.00013/1K = **$0.65/month**
- Chat: 1000 queries × $0.002/query = **$2/month**
- **Total: ~$21/month**

**Milvus (Zilliz Cloud)**:
- Free tier: 1M vectors, 100GB storage
- Sufficient for 1000+ videos
- **Cost: $0/month**

**Server/Hosting**:
- VPS (2 CPU, 4GB RAM): **$10-20/month**
- Docker hosting (DigitalOcean): **$12/month**
- Cloud Functions (GCP/AWS): **$5-15/month**

**Total Estimated Cost**: **$31-56/month** for 100 videos

### Cost Reduction Tips

1. **Reduce check frequency**: Check every 2-4 hours instead of every hour
2. **Skip transcript cleaning**: Set `--no-clean` flag (saves GPT-4 calls)
3. **Batch processing**: Process multiple videos before RAG integration
4. **Cache embeddings**: Avoid regenerating same text embeddings
5. **Use smaller models**: Consider `gpt-3.5-turbo` instead of `gpt-4`
6. **Selective creators**: Focus on high-value channels only

---

## Next Steps

1. ✅ **Customize creators** - Add your favorite music production channels
2. ✅ **Test the pipeline** - Run in test mode with short intervals
3. ✅ **Setup notifications** - Configure Slack/Discord/Email
4. ✅ **Choose deployment** - Pick systemd, Docker, or cron
5. ✅ **Monitor logs** - Set up log rotation and monitoring
6. ✅ **Iterate and improve** - Add features like topic tagging, sentiment analysis

---

## Additional Features to Consider

### 1. Topic Extraction
Automatically tag videos with topics (mixing, mastering, synthesis, etc.):

```python
async def extract_topics(transcript_text: str) -> List[str]:
    """Extract topics from transcript using GPT."""
    response = await openai.ChatCompletion.acreate(
        model="gpt-3.5-turbo",
        messages=[{
            "role": "system",
            "content": "Extract 3-5 main topics from this music production tutorial transcript. Return as comma-separated list."
        }, {
            "role": "user",
            "content": transcript_text[:2000]  # First 2000 chars
        }]
    )
    topics = response.choices[0].message.content.split(',')
    return [topic.strip() for topic in topics]
```

### 2. Duplicate Detection
Detect if a new video covers the same content as existing videos:

```python
async def find_similar_videos(new_video_embedding: list) -> List[Dict]:
    """Find videos with similar content."""
    # Search Milvus for similar embeddings
    results = milvus_client.search(
        collection_name="youtube_creator_videos",
        data=[new_video_embedding],
        limit=5,
        output_fields=["video_title", "channel_name"]
    )
    return results
```

### 3. Scheduled Reports
Send weekly/monthly summary emails:

```python
# Add to automated_pipeline.py
from datetime import datetime

async def send_weekly_report(self):
    """Send weekly summary report."""
    if datetime.now().weekday() == 6:  # Sunday
        stats = self.tracker.get_stats()
        self.notifier.notify_summary({
            'new_videos': stats['total_processed'],
            'total_videos': stats['total_processed'],
            'rag_integrated': stats['rag_integrated'],
            'pending': stats['pending_integration'],
            'errors': stats['recent_errors'],
            'by_creator': stats['by_channel']
        })
```

### 4. Quality Scoring
Score transcript quality and skip low-quality content:

```python
def assess_transcript_quality(transcript: Dict) -> float:
    """Score transcript quality 0-1."""
    score = 0.0

    # Check duration (prefer 10-60 min videos)
    duration_min = transcript['duration'] / 60
    if 10 <= duration_min <= 60:
        score += 0.3

    # Check segment count (more segments = better)
    if len(transcript['segments']) > 20:
        score += 0.3

    # Check word count
    word_count = len(transcript.get('text', '').split())
    if word_count > 500:
        score += 0.4

    return score

# In pipeline
quality_score = assess_transcript_quality(transcript)
if quality_score < 0.5:
    print(f"⚠️  Low quality transcript, skipping...")
    continue
```

---

## Conclusion

You now have a complete guide to convert the YouTube Transcript RAG system into an automated data pipeline for music production tutorials (or any other domain).

**Key Takeaways**:
- ✅ Automated video detection with deduplication
- ✅ Continuous processing with configurable intervals
- ✅ Error handling and retry logic
- ✅ Notifications for new content and errors
- ✅ Multiple deployment options (cron, systemd, Docker, Kubernetes)
- ✅ Monitoring and logging capabilities
- ✅ Cost-effective scaling strategies

**Estimated Setup Time**: 2-4 hours
**Maintenance Time**: 1-2 hours/month

For questions or improvements, refer to the main documentation or create an issue.

---

**Document Version**: 1.0.0
**Last Updated**: 2024-01-15
**Author**: YouTube Transcript RAG System
