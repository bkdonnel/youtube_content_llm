"""
YouTube Music Production Pipeline DAG
Monitors YouTube creators and processes new videos automatically
"""

from airflow import DAG
from airflow.operators.python import PythonOperator
from airflow.sensors.python import PythonSensor
from datetime import datetime, timedelta
from pathlib import Path
import os

# Import from include directory
from include.youtube_transcript_downloader import (
    CREATORS,
    get_channel_videos,
    download_video_audio,
    generate_transcript_with_chunking,
    save_transcript_json,
    create_readable_transcript,
    cleanup_audio_file,
    create_openai_client,
)
from include.add_transcripts_to_rag import process_transcript_file
from include.video_tracker import (
    initialize_database,
    is_video_processed,
    mark_video_processed,
    mark_rag_integrated,
    update_channel_check,
    VideoRecord
)

# Configuration from environment variables
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "/tmp/music_tutorials"))
RAG_API_URL = os.getenv("RAG_API_URL", "http://localhost:8000")
MAX_VIDEOS_PER_CHECK = int(os.getenv("MAX_VIDEOS_PER_CHECK", "5"))

# Default DAG arguments
default_args = {
    'owner': 'airflow',
    'depends_on_past': False,
    'email_on_failure': False,
    'email_on_retry': False,
    'retries': 2,
    'retry_delay': timedelta(minutes=5),
}


def check_for_new_videos(**context):
    """Check all creators for new videos and return list to process."""
    initialize_database()

    new_videos_to_process = []

    for creator_name, creator_info in CREATORS.items():
        print(f"Checking {creator_name}...")

        # Get recent videos
        videos = get_channel_videos(creator_info['url'], MAX_VIDEOS_PER_CHECK * 2)

        # Filter out already processed
        for video in videos:
            if not is_video_processed(video.id):
                new_videos_to_process.append({
                    'creator_name': creator_name,
                    'video': video.dict()
                })

                if len(new_videos_to_process) >= MAX_VIDEOS_PER_CHECK:
                    break

        if len(new_videos_to_process) >= MAX_VIDEOS_PER_CHECK:
            break

    # Push to XCom for next tasks
    context['task_instance'].xcom_push(key='videos_to_process', value=new_videos_to_process)

    print(f"Found {len(new_videos_to_process)} new videos to process")
    return len(new_videos_to_process) > 0


def process_video_task(**context):
    """Download, transcribe, and upload a single video."""
    videos = context['task_instance'].xcom_pull(key='videos_to_process')

    if not videos:
        print("No videos to process")
        return

    openai_client = create_openai_client(OPENAI_API_KEY)

    for item in videos:
        creator_name = item['creator_name']
        video_data = item['video']

        # Reconstruct VideoMetadata object
        from youtube_transcript_downloader import VideoMetadata
        video = VideoMetadata(**video_data)

        try:
            print(f"\nProcessing: {video.title}")

            # Create creator directory
            creator_dir = OUTPUT_DIR / creator_name.replace(" ", "_")
            creator_dir.mkdir(exist_ok=True, parents=True)

            # Download video
            downloaded_info = download_video_audio(video.url, creator_dir)
            if not downloaded_info:
                raise Exception("Failed to download video")

            # Generate transcript
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
                segments_added = process_transcript_file(transcript_file, RAG_API_URL)

                if segments_added > 0:
                    mark_rag_integrated(downloaded_info.video_id)
                    print(f"✅ Added {segments_added} segments to RAG")

            # Clean up audio file
            cleanup_audio_file(downloaded_info.audio_file)

            # Delete transcript files (Milvus has the data)
            if transcript_file.exists():
                transcript_file.unlink()
                print(f"Deleted transcript file (data in Milvus)")

            # Delete readable file too
            readable_file = transcript_file.parent / f"{transcript_file.stem.replace('_transcript', '')}_readable.txt"
            if readable_file.exists():
                readable_file.unlink()

            print(f"✅ Successfully processed: {downloaded_info.title}")

        except Exception as e:
            print(f"❌ Error processing {video.title}: {e}")
            continue


# Define the DAG
with DAG(
    'youtube_music_production_pipeline',
    default_args=default_args,
    description='Monitor YouTube creators and process new music production tutorials',
    schedule_interval='0 23 * * *',  # Run daily at 11 PM
    start_date=datetime(2025, 1, 1),
    catchup=False,
    tags=['youtube', 'music-production', 'rag'],
) as dag:

    # Task 1: Check for new videos
    check_videos = PythonSensor(
        task_id='check_for_new_videos',
        python_callable=check_for_new_videos,
        mode='poke',
        poke_interval=60,  # Check every 60 seconds
        timeout=300,  # Timeout after 5 minutes
    )

    # Task 2: Process videos (download, transcribe, upload to RAG)
    process_videos = PythonOperator(
        task_id='process_videos',
        python_callable=process_video_task,
    )

    # Define task dependencies
    check_videos >> process_videos
