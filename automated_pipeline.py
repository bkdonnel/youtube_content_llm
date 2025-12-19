#!/usr/bin/env python3
"""
Automated Music Production Tutorial Pipeline
Continuously monitors YouTube channels and processes new videos
"""

import os
import sys
import asyncio
import argparse
from pathlib import Path
from datetime import datetime
from typing import Dict, List
from dotenv import load_dotenv
from pydantic import BaseModel

# Import from refactored modules
from youtube_transcript_downloader import (
    CREATORS,
    get_channel_videos,
    download_video_audio,
    generate_transcript_with_chunking,
    save_transcript_json,
    create_readable_transcript,
    cleanup_audio_file,
    create_openai_client,
    VideoMetadata
)
from add_transcripts_to_rag import (
    process_transcript_file
)
from video_tracker import (
    initialize_database,
    is_video_processed,
    mark_video_processed,
    mark_rag_integrated,
    update_channel_check,
    log_processing_error,
    get_processing_stats,
    print_stats,
    VideoRecord
)
from notifications import (
    notify_new_video,
    notify_error,
    VideoInfo,
    ErrorInfo
)

# Load environment variables
load_dotenv()

# Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "music_tutorials"))
RAG_API_URL = os.getenv("RAG_API_URL", "http://localhost:8000")
CHECK_INTERVAL_MINUTES = int(os.getenv("CHECK_INTERVAL_MINUTES", "60"))
MAX_VIDEOS_PER_CHECK = int(os.getenv("MAX_VIDEOS_PER_CHECK", "5"))


# Pydantic Models
class PipelineRunSummary(BaseModel):
    new_videos_found: int
    videos_processed: int
    started_at: str
    completed_at: str


# Video filtering utilities
def filter_new_videos(
    videos: List[VideoMetadata],
    max_videos: int,
    db_path: str = "video_tracker.db"
) -> List[VideoMetadata]:
    """Filter out already processed videos."""
    new_videos = []

    for video in videos:
        if not is_video_processed(video.id, db_path):
            new_videos.append(video)

        if len(new_videos) >= max_videos:
            break

    return new_videos


def get_new_videos_for_creator(
    creator_name: str,
    creator_url: str,
    max_videos: int
) -> List[VideoMetadata]:
    """Check for new videos not in tracker DB."""
    print(f"\n{'='*80}")
    print(f"Checking for new videos: {creator_name}")
    print(f"{'='*80}")

    # Get recent videos from YouTube
    videos = get_channel_videos(creator_url, max_videos * 2)

    # Filter out already processed videos
    new_videos = filter_new_videos(videos, max_videos)

    print(f"Found {len(new_videos)} new video(s)")
    return new_videos


# Video processing workflow
async def process_new_video(
    video: VideoMetadata,
    creator_name: str,
    output_dir: Path,
    openai_client,
    rag_api_url: str
) -> bool:
    """Download, transcribe, and add to RAG."""
    print(f"\nProcessing: {video.title}")

    try:
        # Create creator directory
        creator_dir = output_dir / creator_name.replace(" ", "_")
        creator_dir.mkdir(exist_ok=True, parents=True)

        # Download video
        downloaded_info = download_video_audio(video.url, creator_dir)
        if not downloaded_info:
            raise Exception("Failed to download video")

        # Generate transcript (with automatic chunking for large files)
        transcript = generate_transcript_with_chunking(
            downloaded_info.audio_file,
            downloaded_info.title,
            openai_client
        )
        if not transcript:
            raise Exception("Failed to generate transcript")

        # Save transcript
        transcript_path = save_transcript_json(
            transcript,
            downloaded_info,
            creator_dir
        )

        # Create readable version
        create_readable_transcript(
            transcript,
            downloaded_info,
            creator_dir
        )

        # Mark as processed in tracker
        video_record = VideoRecord(
            video_id=downloaded_info.video_id,
            channel_name=creator_name,
            video_title=downloaded_info.title,
            upload_date=downloaded_info.upload_date or '',
            transcript_path=transcript_path,
            rag_integrated=False
        )
        mark_video_processed(video_record)

        # Add to RAG system
        transcript_file = Path(transcript_path)
        if transcript_file.exists():
            segments_added = process_transcript_file(transcript_file, rag_api_url)

            if segments_added > 0:
                mark_rag_integrated(downloaded_info.video_id)

        # Clean up audio file
        cleanup_audio_file(downloaded_info.audio_file)

        # Send notification
        notify_new_video(VideoInfo(
            creator=creator_name,
            title=downloaded_info.title,
            id=downloaded_info.video_id,
            url=downloaded_info.url,
            duration=float(downloaded_info.duration)
        ))

        print(f"✅ Successfully processed: {downloaded_info.title}")
        return True

    except Exception as e:
        error_msg = str(e)
        print(f"❌ Error processing video: {error_msg}")

        # Log error
        log_processing_error(
            video_id=video.id,
            channel_name=creator_name,
            error_message=error_msg
        )

        # Send error notification
        notify_error(ErrorInfo(
            creator=creator_name,
            video_title=video.title,
            video_id=video.id,
            error=error_msg
        ))

        return False


# Creator processing
async def process_creator(
    creator_name: str,
    creator_info: Dict[str, str],
    output_dir: Path,
    openai_client,
    rag_api_url: str,
    max_videos: int
) -> int:
    """Process new videos for a single creator."""
    try:
        # Get new videos
        new_videos = get_new_videos_for_creator(
            creator_name,
            creator_info['url'],
            max_videos
        )

        if not new_videos:
            return 0

        # Process each new video
        processed_count = 0
        for video in new_videos:
            success = await process_new_video(
                video,
                creator_name,
                output_dir,
                openai_client,
                rag_api_url
            )
            if success:
                processed_count += 1

        # Update channel check time
        last_video_id = new_videos[0].id if new_videos else None
        update_channel_check(creator_name, last_video_id)

        return processed_count

    except Exception as e:
        print(f"Error processing creator {creator_name}: {e}")
        return 0


# Main pipeline workflows
async def run_pipeline_once(
    creators: Dict[str, Dict[str, str]],
    output_dir: Path,
    openai_api_key: str,
    rag_api_url: str,
    max_videos_per_check: int
) -> PipelineRunSummary:
    """Main pipeline run - check all creators."""
    started_at = datetime.now()

    print("\n" + "🎵"*40)
    print("MUSIC PRODUCTION PIPELINE - AUTOMATED RUN")
    print(f"Started at: {started_at.strftime('%Y-%m-%d %H:%M:%S')}")
    print("🎵"*40)

    openai_client = create_openai_client(openai_api_key)

    total_new_videos = 0
    total_processed = 0

    for creator_name, creator_info in creators.items():
        processed = await process_creator(
            creator_name,
            creator_info,
            output_dir,
            openai_client,
            rag_api_url,
            max_videos_per_check
        )
        total_processed += processed

    completed_at = datetime.now()

    # Print summary
    print(f"\n{'='*80}")
    print("RUN COMPLETE")
    print(f"{'='*80}")
    print(f"New videos found: {total_new_videos}")
    print(f"Successfully processed: {total_processed}")
    print(f"Completed at: {completed_at.strftime('%Y-%m-%d %H:%M:%S')}")

    # Get stats
    stats = get_processing_stats()
    print(f"\nDatabase Statistics:")
    print(f"  Total videos: {stats.total_processed}")
    print(f"  RAG integrated: {stats.rag_integrated}")
    print(f"  Pending: {stats.pending_integration}")

    return PipelineRunSummary(
        new_videos_found=total_new_videos,
        videos_processed=total_processed,
        started_at=started_at.isoformat(),
        completed_at=completed_at.isoformat()
    )


async def run_pipeline_continuous(
    creators: Dict[str, Dict[str, str]],
    output_dir: Path,
    openai_api_key: str,
    rag_api_url: str,
    max_videos_per_check: int,
    check_interval_minutes: int
) -> None:
    """Run pipeline continuously at intervals."""
    print(f"\n🔄 Starting continuous mode (checking every {check_interval_minutes} minutes)")
    print("Press Ctrl+C to stop\n")

    try:
        while True:
            await run_pipeline_once(
                creators,
                output_dir,
                openai_api_key,
                rag_api_url,
                max_videos_per_check
            )

            print(f"\n😴 Sleeping for {check_interval_minutes} minutes...")
            await asyncio.sleep(check_interval_minutes * 60)

    except KeyboardInterrupt:
        print("\n\n✋ Pipeline stopped by user")


def show_pipeline_stats() -> None:
    """Display pipeline statistics."""
    stats = get_processing_stats()

    print("\n" + "="*80)
    print("📊 PIPELINE STATISTICS")
    print("="*80)
    print_stats(stats)
    print("="*80)


# CLI utilities
def parse_arguments() -> argparse.Namespace:
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Automated Music Production Tutorial Pipeline"
    )
    parser.add_argument(
        '--continuous',
        action='store_true',
        help='Run continuously at intervals'
    )
    parser.add_argument(
        '--interval',
        type=int,
        default=CHECK_INTERVAL_MINUTES,
        help=f'Check interval in minutes (default: {CHECK_INTERVAL_MINUTES})'
    )
    parser.add_argument(
        '--stats',
        action='store_true',
        help='Show statistics and exit'
    )

    return parser.parse_args()


def validate_environment() -> bool:
    """Check required environment variables."""
    if not OPENAI_API_KEY:
        print("Error: OPENAI_API_KEY not set in environment variables")
        return False
    return True


def main() -> None:
    """Main entry point."""
    args = parse_arguments()

    # Validate environment
    if not validate_environment():
        sys.exit(1)

    # Initialize database
    initialize_database()

    # Show stats and exit
    if args.stats:
        show_pipeline_stats()
        return

    # Ensure output directory exists
    OUTPUT_DIR.mkdir(exist_ok=True, parents=True)

    # Run pipeline
    if args.continuous:
        asyncio.run(run_pipeline_continuous(
            creators=CREATORS,
            output_dir=OUTPUT_DIR,
            openai_api_key=OPENAI_API_KEY,
            rag_api_url=RAG_API_URL,
            max_videos_per_check=MAX_VIDEOS_PER_CHECK,
            check_interval_minutes=args.interval
        ))
    else:
        asyncio.run(run_pipeline_once(
            creators=CREATORS,
            output_dir=OUTPUT_DIR,
            openai_api_key=OPENAI_API_KEY,
            rag_api_url=RAG_API_URL,
            max_videos_per_check=MAX_VIDEOS_PER_CHECK
        ))


if __name__ == "__main__":
    main()
