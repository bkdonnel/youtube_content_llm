#!/usr/bin/env python3
"""
Video Tracker Database
Tracks processed videos to avoid duplicates and manage pipeline state
"""

import sqlite3
from pathlib import Path
from typing import List, Dict, Optional, Tuple
from datetime import datetime
from pydantic import BaseModel


# Pydantic Models
class VideoRecord(BaseModel):
    video_id: str
    channel_name: str
    video_title: str
    upload_date: str
    transcript_path: str
    rag_integrated: bool = False


class ProcessingStats(BaseModel):
    total_processed: int
    rag_integrated: int
    pending_integration: int
    by_channel: Dict[str, int]
    recent_errors: int


# Database utilities
def get_database_connection(db_path: str = "video_tracker.db") -> sqlite3.Connection:
    """Get database connection."""
    return sqlite3.connect(db_path)


def initialize_database(db_path: str = "video_tracker.db") -> None:
    """Create database tables if they don't exist."""
    conn = get_database_connection(db_path)
    cursor = conn.cursor()

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

    conn.commit()
    conn.close()


def is_video_processed(video_id: str, db_path: str = "video_tracker.db") -> bool:
    """Check if a video has already been processed."""
    conn = get_database_connection(db_path)
    cursor = conn.cursor()

    cursor.execute(
        "SELECT COUNT(*) FROM processed_videos WHERE video_id = ?",
        (video_id,)
    )
    count = cursor.fetchone()[0]
    conn.close()

    return count > 0


def mark_video_processed(
    video_record: VideoRecord,
    db_path: str = "video_tracker.db"
) -> None:
    """Mark a video as processed."""
    conn = get_database_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT OR REPLACE INTO processed_videos
        (video_id, channel_name, video_title, upload_date, transcript_path, rag_integrated)
        VALUES (?, ?, ?, ?, ?, ?)
    """, (
        video_record.video_id,
        video_record.channel_name,
        video_record.video_title,
        video_record.upload_date,
        video_record.transcript_path,
        video_record.rag_integrated
    ))

    conn.commit()
    conn.close()


def mark_rag_integrated(video_id: str, db_path: str = "video_tracker.db") -> None:
    """Mark a video as integrated into RAG system."""
    conn = get_database_connection(db_path)
    cursor = conn.cursor()

    cursor.execute(
        "UPDATE processed_videos SET rag_integrated = 1 WHERE video_id = ?",
        (video_id,)
    )

    conn.commit()
    conn.close()


def get_unintegrated_videos(db_path: str = "video_tracker.db") -> List[Dict[str, str]]:
    """Get videos that have been transcribed but not added to RAG."""
    conn = get_database_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        SELECT video_id, channel_name, video_title, transcript_path
        FROM processed_videos
        WHERE rag_integrated = 0
    """)

    results = cursor.fetchall()
    conn.close()

    return [
        {
            'video_id': row[0],
            'channel_name': row[1],
            'video_title': row[2],
            'transcript_path': row[3]
        }
        for row in results
    ]


def log_processing_error(
    video_id: str,
    channel_name: str,
    error_message: str,
    db_path: str = "video_tracker.db"
) -> None:
    """Log a processing error."""
    conn = get_database_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO processing_errors (video_id, channel_name, error_message)
        VALUES (?, ?, ?)
    """, (video_id, channel_name, error_message))

    conn.commit()
    conn.close()


def update_channel_check(
    channel_name: str,
    last_video_id: Optional[str] = None,
    db_path: str = "video_tracker.db"
) -> None:
    """Update the last check time for a channel."""
    conn = get_database_connection(db_path)
    cursor = conn.cursor()

    cursor.execute("""
        INSERT OR REPLACE INTO channel_checks (channel_name, last_checked, last_video_id)
        VALUES (?, CURRENT_TIMESTAMP, ?)
    """, (channel_name, last_video_id))

    conn.commit()
    conn.close()


def get_processing_stats(db_path: str = "video_tracker.db") -> ProcessingStats:
    """Get processing statistics."""
    conn = get_database_connection(db_path)
    cursor = conn.cursor()

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

    conn.close()

    return ProcessingStats(
        total_processed=total_processed,
        rag_integrated=rag_integrated,
        pending_integration=total_processed - rag_integrated,
        by_channel=by_channel,
        recent_errors=recent_errors
    )


def print_stats(stats: ProcessingStats) -> None:
    """Print processing statistics."""
    print("📊 Pipeline Statistics:")
    print(f"   Total processed: {stats.total_processed}")
    print(f"   RAG integrated: {stats.rag_integrated}")
    print(f"   Pending: {stats.pending_integration}")
    print(f"   Recent errors: {stats.recent_errors}")

    if stats.by_channel:
        print("\n📺 By Channel:")
        for channel, count in stats.by_channel.items():
            print(f"   {channel}: {count} videos")


# Example usage
if __name__ == "__main__":
    # Initialize database
    initialize_database()

    # Get statistics
    stats = get_processing_stats()
    print_stats(stats)
