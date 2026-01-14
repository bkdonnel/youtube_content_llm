#!/usr/bin/env python3
"""
YouTube Transcript Downloader for Music Production Tutorials
Downloads videos from specified music production creators and generates transcripts using OpenAI Whisper
"""

import os
import json
import subprocess
import base64
import tempfile
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional
import yt_dlp
from openai import OpenAI
from dotenv import load_dotenv
from pydantic import BaseModel
from googleapiclient.discovery import build

# Load environment variables
load_dotenv()

# Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
YOUTUBE_API_KEY = os.getenv("YOUTUBE_API_KEY")
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "music_tutorials"))
MAX_VIDEOS_PER_CREATOR = 5
MAX_AUDIO_SIZE_MB = 24  # Whisper API limit is 25 MB, use 24 to be safe
CHUNK_DURATION_MINUTES = 20  # Duration of each audio chunk for large files

# Music Production Creators Configuration
CREATORS = {
    "Zen World": {
        "url": "https://www.youtube.com/@ZenWorld",
        "description": "Tutorials on arrangement, sound design, tech house and techno"
    },
    "Alice Efe": {
        "url": "https://www.youtube.com/@Alice-Efe",
        "description": "Music production tutorials"
    }
}


# Pydantic Models
class VideoMetadata(BaseModel):
    id: str
    title: str
    url: str


class DownloadedVideo(BaseModel):
    video_id: str
    title: str
    url: str
    duration: int
    upload_date: Optional[str] = None
    audio_file: str
    thumbnail: Optional[str] = None


class TranscriptData(BaseModel):
    text: str
    language: str
    duration: float
    segments: List[Dict]
    words: Optional[List[Dict]] = None


class ProcessingSummary(BaseModel):
    total_creators: int
    total_videos_processed: int
    creators_processed: Dict[str, int]
    timestamp: str


# YouTube utilities
def get_channel_id_from_url(channel_url: str, youtube_api: any) -> Optional[str]:
    """Extract channel ID from various YouTube URL formats."""
    try:
        # Extract username/handle from URL
        # Formats: youtube.com/@username or youtube.com/c/channelname or youtube.com/user/username
        if '@' in channel_url:
            # Handle format: youtube.com/@username
            handle = channel_url.split('@')[-1].rstrip('/')

            # Use YouTube API to search for channel by handle
            request = youtube_api.search().list(
                part='snippet',
                q=handle,
                type='channel',
                maxResults=1
            )
            response = request.execute()

            if response['items']:
                return response['items'][0]['snippet']['channelId']

        # Try to get channel ID from forUsername or custom URL
        # This is a fallback for other URL formats
        return None

    except Exception as e:
        print(f"  Error extracting channel ID: {e}")
        return None


def get_channel_videos(channel_url: str, max_videos: int = 5) -> List[VideoMetadata]:
    """Fetch video metadata from a channel using YouTube Data API v3. Filters out YouTube Shorts."""

    if not YOUTUBE_API_KEY:
        print("Error: YOUTUBE_API_KEY not set. Cannot fetch channel videos.")
        return []

    print(f"Fetching videos from: {channel_url}")

    try:
        # Create YouTube API client
        youtube = build('youtube', 'v3', developerKey=YOUTUBE_API_KEY)

        # Get channel ID from URL
        channel_id = get_channel_id_from_url(channel_url, youtube)

        if not channel_id:
            print(f"  Error: Could not extract channel ID from URL")
            return []

        print(f"  Channel ID: {channel_id}")

        # Get channel's uploads playlist ID
        channel_request = youtube.channels().list(
            part='contentDetails',
            id=channel_id
        )
        channel_response = channel_request.execute()

        if not channel_response['items']:
            print(f"  Error: Could not find channel")
            return []

        uploads_playlist_id = channel_response['items'][0]['contentDetails']['relatedPlaylists']['uploads']

        # Get recent videos from uploads playlist
        # Fetch more than needed to account for shorts we'll filter out
        playlist_request = youtube.playlistItems().list(
            part='snippet',
            playlistId=uploads_playlist_id,
            maxResults=min(max_videos * 3, 50)  # API max is 50
        )
        playlist_response = playlist_request.execute()

        if not playlist_response['items']:
            print(f"  No videos found")
            return []

        # Extract video IDs
        video_ids = [item['snippet']['resourceId']['videoId'] for item in playlist_response['items']]

        # Get video details (including duration) for all videos at once
        videos_request = youtube.videos().list(
            part='contentDetails,snippet',
            id=','.join(video_ids)
        )
        videos_response = videos_request.execute()

        videos = []
        shorts_filtered = 0

        for video_item in videos_response['items']:
            # Parse ISO 8601 duration (e.g., "PT15M33S" = 15 minutes 33 seconds)
            duration_str = video_item['contentDetails']['duration']
            duration_seconds = parse_duration(duration_str)

            # Filter out YouTube Shorts (videos 60 seconds or less)
            if duration_seconds <= 60:
                shorts_filtered += 1
                print(f"  Skipping Short: {video_item['snippet']['title']} ({duration_seconds}s)")
                continue

            videos.append(VideoMetadata(
                id=video_item['id'],
                title=video_item['snippet']['title'],
                url=f"https://www.youtube.com/watch?v={video_item['id']}"
            ))

            if len(videos) >= max_videos:
                break

        if shorts_filtered > 0:
            print(f"  Filtered out {shorts_filtered} Shorts")

        print(f"  Found {len(videos)} videos (after filtering)")
        return videos

    except Exception as e:
        print(f"Error fetching channel videos: {e}")
        import traceback
        traceback.print_exc()
        return []


def parse_duration(duration: str) -> int:
    """Parse ISO 8601 duration string to seconds.
    Example: PT15M33S -> 933 seconds
    """
    import re

    # Remove 'PT' prefix
    duration = duration.replace('PT', '')

    # Extract hours, minutes, seconds
    hours = 0
    minutes = 0
    seconds = 0

    # Match patterns
    hour_match = re.search(r'(\d+)H', duration)
    minute_match = re.search(r'(\d+)M', duration)
    second_match = re.search(r'(\d+)S', duration)

    if hour_match:
        hours = int(hour_match.group(1))
    if minute_match:
        minutes = int(minute_match.group(1))
    if second_match:
        seconds = int(second_match.group(1))

    return hours * 3600 + minutes * 60 + seconds


def download_video_audio(video_url: str, creator_dir: Path) -> Optional[DownloadedVideo]:
    """Download audio from a YouTube video."""
    print(f"  Downloading: {video_url}")

    ydl_opts = {
        'format': 'bestaudio[ext=m4a]/bestaudio',
        'outtmpl': str(creator_dir / '%(id)s.%(ext)s'),
        'quiet': False,
        'writeinfojson': True,
        'writethumbnail': True,
        # Add browser-like behavior to avoid bot detection
        'user_agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
        'extractor_args': {
            'youtube': {
                'player_client': ['ios', 'web'],
                'player_skip': ['webpage'],
            }
        },
        # Add sleep intervals to avoid rate limiting
        'sleep_interval': 1,
        'max_sleep_interval': 3,
        # Retry on errors
        'retries': 3,
    }

    # Handle YouTube cookies for authentication
    cookies_file = None
    youtube_cookies_b64 = os.getenv("YOUTUBE_COOKIES_B64")

    if youtube_cookies_b64:
        try:
            # Decode base64 cookies and write to temporary file
            cookies_content = base64.b64decode(youtube_cookies_b64).decode('utf-8')

            # Create temporary file for cookies
            fd, cookies_file = tempfile.mkstemp(suffix='.txt', prefix='yt_cookies_')
            with os.fdopen(fd, 'w') as f:
                f.write(cookies_content)

            ydl_opts['cookiefile'] = cookies_file
            print(f"  Using YouTube cookies for authentication")
        except Exception as e:
            print(f"  Warning: Could not load YouTube cookies: {e}")

    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(video_url, download=True)

            # Find the downloaded audio file
            audio_file = None
            for ext in ['m4a', 'mp3', 'webm']:
                file_path = creator_dir / f"{info['id']}.{ext}"
                if file_path.exists():
                    audio_file = str(file_path)
                    break

            if not audio_file:
                print(f"  Warning: Could not find audio file")
                return None

            thumbnail_path = creator_dir / f"{info['id']}.jpg"

            return DownloadedVideo(
                video_id=info['id'],
                title=info['title'],
                url=info['webpage_url'],
                duration=info.get('duration', 0),
                upload_date=info.get('upload_date'),
                audio_file=audio_file,
                thumbnail=str(thumbnail_path) if thumbnail_path.exists() else None
            )

    except Exception as e:
        print(f"  Error downloading video: {e}")
        return None
    finally:
        # Clean up cookies file
        if cookies_file and os.path.exists(cookies_file):
            try:
                os.remove(cookies_file)
            except:
                pass


# Transcription utilities
def create_openai_client(api_key: str) -> OpenAI:
    """Create OpenAI client."""
    return OpenAI(api_key=api_key)


def get_audio_duration(audio_file: str) -> float:
    """Get duration of audio file in seconds using ffprobe."""
    try:
        result = subprocess.run(
            [
                'ffprobe',
                '-v', 'error',
                '-show_entries', 'format=duration',
                '-of', 'default=noprint_wrappers=1:nokey=1',
                audio_file
            ],
            capture_output=True,
            text=True,
            check=True
        )
        return float(result.stdout.strip())
    except Exception as e:
        print(f"  Error getting audio duration: {e}")
        return 0


def split_audio_file(audio_file: str, chunk_duration_minutes: int = 20) -> List[str]:
    """Split audio file into chunks of specified duration."""
    audio_path = Path(audio_file)
    file_size_mb = audio_path.stat().st_size / (1024 * 1024)

    print(f"  Audio file size: {file_size_mb:.2f} MB")

    if file_size_mb <= MAX_AUDIO_SIZE_MB:
        return [audio_file]

    print(f"  File exceeds {MAX_AUDIO_SIZE_MB} MB limit. Splitting into chunks...")

    duration = get_audio_duration(audio_file)
    if duration == 0:
        print("  Warning: Could not determine audio duration")
        return [audio_file]

    chunk_duration_seconds = chunk_duration_minutes * 60
    num_chunks = int(duration / chunk_duration_seconds) + 1

    print(f"  Total duration: {duration/60:.1f} minutes")
    print(f"  Creating {num_chunks} chunks of ~{chunk_duration_minutes} minutes each")

    chunks = []
    for i in range(num_chunks):
        start_time = i * chunk_duration_seconds
        chunk_file = audio_path.parent / f"{audio_path.stem}_chunk_{i+1}{audio_path.suffix}"

        try:
            subprocess.run(
                [
                    'ffmpeg',
                    '-i', audio_file,
                    '-ss', str(start_time),
                    '-t', str(chunk_duration_seconds),
                    '-c', 'copy',
                    '-y',
                    str(chunk_file)
                ],
                capture_output=True,
                check=True
            )
            chunks.append(str(chunk_file))
            chunk_size_mb = chunk_file.stat().st_size / (1024 * 1024)
            print(f"  Created chunk {i+1}/{num_chunks}: {chunk_size_mb:.2f} MB")
        except Exception as e:
            print(f"  Error creating chunk {i+1}: {e}")

    return chunks if chunks else [audio_file]


def generate_transcript(
    audio_file: str,
    video_title: str,
    openai_client: OpenAI
) -> Optional[TranscriptData]:
    """Generate transcript using OpenAI Whisper."""
    print(f"  Transcribing: {video_title}")

    try:
        with open(audio_file, 'rb') as audio:
            transcript = openai_client.audio.transcriptions.create(
                model="whisper-1",
                file=audio,
                response_format="verbose_json",
                timestamp_granularities=["segment", "word"]
            )

        # Convert to dict
        transcript_dict = transcript.model_dump() if hasattr(transcript, 'model_dump') else transcript

        print(f"  Transcription complete! ({len(transcript_dict.get('segments', []))} segments)")

        return TranscriptData(
            text=transcript_dict.get('text', ''),
            language=transcript_dict.get('language', 'en'),
            duration=transcript_dict.get('duration', 0),
            segments=transcript_dict.get('segments', []),
            words=transcript_dict.get('words')
        )

    except Exception as e:
        print(f"  Error during transcription: {e}")
        return None


def merge_transcripts(chunk_transcripts: List[TranscriptData], chunk_duration_minutes: int) -> TranscriptData:
    """Merge multiple transcript chunks into a single transcript with adjusted timestamps."""
    if len(chunk_transcripts) == 1:
        return chunk_transcripts[0]

    merged_text = ""
    merged_segments = []
    merged_words = []
    total_duration = 0
    chunk_duration_seconds = chunk_duration_minutes * 60

    for chunk_idx, chunk in enumerate(chunk_transcripts):
        time_offset = chunk_idx * chunk_duration_seconds

        # Add text with space
        if merged_text:
            merged_text += " "
        merged_text += chunk.text

        # Adjust segment timestamps
        for segment in chunk.segments:
            adjusted_segment = segment.copy()
            adjusted_segment['start'] = segment['start'] + time_offset
            adjusted_segment['end'] = segment['end'] + time_offset
            merged_segments.append(adjusted_segment)

        # Adjust word timestamps if available
        if chunk.words:
            for word in chunk.words:
                adjusted_word = word.copy()
                adjusted_word['start'] = word['start'] + time_offset
                adjusted_word['end'] = word['end'] + time_offset
                merged_words.append(adjusted_word)

        total_duration = max(total_duration, chunk.duration + time_offset)

    return TranscriptData(
        text=merged_text,
        language=chunk_transcripts[0].language,
        duration=total_duration,
        segments=merged_segments,
        words=merged_words if merged_words else None
    )


def generate_transcript_with_chunking(
    audio_file: str,
    video_title: str,
    openai_client: OpenAI
) -> Optional[TranscriptData]:
    """Generate transcript with automatic chunking for large files."""
    # Split audio if needed
    chunk_files = split_audio_file(audio_file, CHUNK_DURATION_MINUTES)

    if len(chunk_files) == 1:
        # Single file, use normal transcription
        return generate_transcript(audio_file, video_title, openai_client)

    # Multiple chunks - transcribe each
    print(f"  Transcribing {len(chunk_files)} chunks for: {video_title}")
    chunk_transcripts = []

    for idx, chunk_file in enumerate(chunk_files, 1):
        print(f"  Transcribing chunk {idx}/{len(chunk_files)}...")
        transcript = generate_transcript(chunk_file, f"{video_title} (chunk {idx})", openai_client)

        if transcript:
            chunk_transcripts.append(transcript)
        else:
            print(f"  Warning: Failed to transcribe chunk {idx}")

        # Clean up chunk file
        try:
            if chunk_file != audio_file:  # Don't delete original
                os.remove(chunk_file)
                print(f"  Cleaned up chunk {idx}")
        except Exception as e:
            print(f"  Warning: Could not delete chunk file: {e}")

    if not chunk_transcripts:
        print("  Error: No chunks were successfully transcribed")
        return None

    # Merge all transcripts
    print(f"  Merging {len(chunk_transcripts)} transcript chunks...")
    merged = merge_transcripts(chunk_transcripts, CHUNK_DURATION_MINUTES)
    print(f"  Merge complete! Total duration: {merged.duration/60:.1f} minutes")

    return merged


# File I/O utilities
def save_transcript_json(
    transcript: TranscriptData,
    video_info: DownloadedVideo,
    creator_dir: Path
) -> str:
    """Save transcript to JSON file."""
    transcripts_dir = creator_dir / "transcripts"
    transcripts_dir.mkdir(exist_ok=True)

    json_file = transcripts_dir / f"{video_info.video_id}_transcript.json"

    transcript_data = {
        'video_id': video_info.video_id,
        'title': video_info.title,
        'url': video_info.url,
        'duration': video_info.duration,
        'upload_date': video_info.upload_date,
        'transcript': transcript.dict()
    }

    with open(json_file, 'w', encoding='utf-8') as f:
        json.dump(transcript_data, f, indent=2, ensure_ascii=False)

    print(f"  Saved transcript: {json_file}")
    return str(json_file)


def create_readable_transcript(
    transcript: TranscriptData,
    video_info: DownloadedVideo,
    creator_dir: Path
) -> None:
    """Create a human-readable text version of the transcript."""
    transcripts_dir = creator_dir / "transcripts"
    txt_file = transcripts_dir / f"{video_info.video_id}_readable.txt"

    with open(txt_file, 'w', encoding='utf-8') as f:
        f.write(f"Video: {video_info.title}\n")
        f.write(f"URL: {video_info.url}\n")
        f.write(f"Duration: {video_info.duration / 60:.1f} minutes\n")
        f.write("="*80 + "\n\n")

        for segment in transcript.segments:
            start = segment.get('start', 0)
            minutes = int(start // 60)
            seconds = int(start % 60)
            timestamp = f"[{minutes:02d}:{seconds:02d}]"
            text = segment.get('text', '').strip()
            f.write(f"{timestamp} {text}\n\n")

    print(f"  Saved readable transcript: {txt_file}")


def cleanup_audio_file(audio_file: str) -> None:
    """Remove audio file to save space."""
    if os.path.exists(audio_file):
        os.remove(audio_file)
        print(f"  Cleaned up audio file")


# Processing workflows
def process_single_video(
    video: VideoMetadata,
    creator_dir: Path,
    openai_client: OpenAI
) -> bool:
    """Process a single video: download, transcribe, save."""
    # Download video
    video_info = download_video_audio(video.url, creator_dir)
    if not video_info:
        return False

    # Generate transcript (with automatic chunking for large files)
    transcript = generate_transcript_with_chunking(
        video_info.audio_file,
        video_info.title,
        openai_client
    )
    if not transcript:
        return False

    # Save transcript files
    save_transcript_json(transcript, video_info, creator_dir)
    create_readable_transcript(transcript, video_info, creator_dir)

    # Clean up audio file
    cleanup_audio_file(video_info.audio_file)

    return True


def process_creator(
    creator_name: str,
    creator_info: Dict[str, str],
    output_dir: Path,
    openai_client: OpenAI,
    max_videos: int = 5
) -> int:
    """Process all videos for a single creator."""
    print(f"\n{'='*80}")
    print(f"Processing Creator: {creator_name}")
    print(f"Description: {creator_info['description']}")
    print(f"{'='*80}")

    # Create creator directory
    creator_dir = output_dir / creator_name.replace(" ", "_")
    creator_dir.mkdir(exist_ok=True, parents=True)

    # Get recent videos
    videos = get_channel_videos(creator_info['url'], max_videos)
    print(f"Found {len(videos)} videos")

    processed_count = 0
    for idx, video in enumerate(videos, 1):
        print(f"\nVideo {idx}/{len(videos)}: {video.title}")

        if process_single_video(video, creator_dir, openai_client):
            processed_count += 1

    print(f"\nProcessed {processed_count}/{len(videos)} videos for {creator_name}")
    return processed_count


def process_all_creators(
    creators: Dict[str, Dict[str, str]],
    output_dir: Path,
    openai_api_key: str,
    max_videos_per_creator: int = 5
) -> ProcessingSummary:
    """Process all configured creators."""
    print("\n" + "🎵"*40)
    print("MUSIC PRODUCTION TUTORIAL TRANSCRIPT DOWNLOADER")
    print("🎵"*40)

    openai_client = create_openai_client(openai_api_key)

    summary = ProcessingSummary(
        total_creators=len(creators),
        total_videos_processed=0,
        creators_processed={},
        timestamp=datetime.now().isoformat()
    )

    for creator_name, creator_info in creators.items():
        try:
            count = process_creator(
                creator_name,
                creator_info,
                output_dir,
                openai_client,
                max_videos_per_creator
            )
            summary.creators_processed[creator_name] = count
            summary.total_videos_processed += count
        except Exception as e:
            print(f"Error processing {creator_name}: {e}")
            summary.creators_processed[creator_name] = 0

    # Save summary
    summary_file = output_dir / "processing_summary.json"
    with open(summary_file, 'w') as f:
        json.dump(summary.dict(), f, indent=2)

    print(f"\n{'='*80}")
    print("PROCESSING COMPLETE")
    print(f"{'='*80}")
    print(f"Total creators: {summary.total_creators}")
    print(f"Total videos processed: {summary.total_videos_processed}")
    print(f"Summary saved to: {summary_file}")

    return summary


def main() -> None:
    """Main entry point."""
    if not OPENAI_API_KEY:
        print("Error: OPENAI_API_KEY not set in environment variables")
        return

    OUTPUT_DIR.mkdir(exist_ok=True, parents=True)

    process_all_creators(
        creators=CREATORS,
        output_dir=OUTPUT_DIR,
        openai_api_key=OPENAI_API_KEY,
        max_videos_per_creator=MAX_VIDEOS_PER_CREATOR
    )


if __name__ == "__main__":
    main()
