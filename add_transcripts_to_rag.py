#!/usr/bin/env python3
"""
Add Transcripts to RAG System
Processes transcript files and adds them to the Milvus vector database for semantic search
"""

import os
import json
import subprocess
from pathlib import Path
from typing import Dict, List, Optional
import requests
from openai import OpenAI
from dotenv import load_dotenv
from pydantic import BaseModel

# Load environment variables
load_dotenv()

# Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "music_tutorials"))
# Use 'api' hostname when running in Docker, localhost otherwise
RAG_API_URL = os.getenv("RAG_API_URL", "http://api:8000" if os.path.exists("/.dockerenv") else "http://localhost:8000")
MAX_CHUNK_DURATION = 25 * 60  # 25 minutes in seconds (Whisper API limit)


# Pydantic Models
class TranscriptSegment(BaseModel):
    text: str
    metadata: str  # JSON string


class IntegrationSummary(BaseModel):
    total_transcripts: int
    total_segments_added: int


# File utilities
def find_transcript_files(output_dir: Path) -> List[Path]:
    """Scan directories for transcript JSON files."""
    transcript_files = []

    for creator_dir in output_dir.iterdir():
        if not creator_dir.is_dir():
            continue

        transcripts_dir = creator_dir / "transcripts"
        if not transcripts_dir.exists():
            continue

        for file in transcripts_dir.glob("*_transcript.json"):
            transcript_files.append(file)

    return transcript_files


def find_unprocessed_audio_files(output_dir: Path) -> List[Path]:
    """Find unprocessed audio files."""
    m4a_files = []

    for creator_dir in output_dir.iterdir():
        if not creator_dir.is_dir():
            continue

        for file in creator_dir.glob("*.m4a"):
            # Check if transcript already exists
            transcripts_dir = creator_dir / "transcripts"
            transcript_file = transcripts_dir / f"{file.stem}_transcript.json"

            if not transcript_file.exists():
                m4a_files.append(file)

    return m4a_files


# Audio processing utilities
def get_audio_duration(audio_file: Path) -> float:
    """Get audio file duration using ffprobe."""
    cmd_duration = [
        'ffprobe', '-v', 'error', '-show_entries', 'format=duration',
        '-of', 'default=noprint_wrappers=1:nokey=1', str(audio_file)
    ]

    try:
        result = subprocess.run(cmd_duration, capture_output=True, text=True, check=True)
        return float(result.stdout.strip())
    except Exception as e:
        print(f"  Error getting duration: {e}")
        return 0


def split_audio_file(audio_file: Path, chunk_duration: int) -> List[Path]:
    """Split large audio file using ffmpeg."""
    print(f"  Splitting audio file into {chunk_duration/60:.0f}-minute chunks...")

    total_duration = get_audio_duration(audio_file)
    if total_duration == 0:
        return []

    # Calculate number of chunks
    num_chunks = int(total_duration // chunk_duration) + 1
    chunks = []

    for i in range(num_chunks):
        start_time = i * chunk_duration
        chunk_file = audio_file.parent / f"{audio_file.stem}_chunk{i}.m4a"

        cmd_split = [
            'ffmpeg', '-i', str(audio_file),
            '-ss', str(start_time), '-t', str(chunk_duration),
            '-c', 'copy', str(chunk_file), '-y'
        ]

        try:
            subprocess.run(cmd_split, capture_output=True, check=True)
            chunks.append(chunk_file)
            print(f"  Created chunk {i+1}/{num_chunks}")
        except Exception as e:
            print(f"  Error creating chunk {i}: {e}")

    return chunks


def create_openai_client(api_key: str) -> OpenAI:
    """Create OpenAI client."""
    return OpenAI(api_key=api_key)


def transcribe_audio_file(
    audio_file: Path,
    openai_client: OpenAI,
    max_chunk_duration: int
) -> Optional[Dict]:
    """Generate transcript from audio file using Whisper."""
    print(f"  Transcribing: {audio_file.name}")

    duration = get_audio_duration(audio_file)

    # Split if too large
    if duration > max_chunk_duration:
        print(f"  Audio file is {duration/60:.1f} minutes, splitting...")
        chunks = split_audio_file(audio_file, max_chunk_duration)

        if not chunks:
            return None

        # Transcribe each chunk
        all_segments = []
        time_offset = 0

        for chunk in chunks:
            try:
                with open(chunk, 'rb') as audio:
                    transcript = openai_client.audio.transcriptions.create(
                        model="whisper-1",
                        file=audio,
                        response_format="verbose_json",
                        timestamp_granularities=["segment", "word"]
                    )

                transcript_dict = transcript.model_dump() if hasattr(transcript, 'model_dump') else transcript

                # Adjust timestamps
                for segment in transcript_dict.get('segments', []):
                    segment['start'] += time_offset
                    segment['end'] += time_offset
                    if 'words' in segment:
                        for word in segment['words']:
                            word['start'] += time_offset
                            word['end'] += time_offset
                    all_segments.append(segment)

                time_offset += max_chunk_duration

                # Clean up chunk
                chunk.unlink()

            except Exception as e:
                print(f"  Error transcribing chunk {chunk}: {e}")
                continue

        return {
            'text': ' '.join(s.get('text', '') for s in all_segments),
            'segments': all_segments,
            'duration': duration,
            'language': all_segments[0].get('language', 'en') if all_segments else 'en'
        }

    else:
        # Transcribe normally
        try:
            with open(audio_file, 'rb') as audio:
                transcript = openai_client.audio.transcriptions.create(
                    model="whisper-1",
                    file=audio,
                    response_format="verbose_json",
                    timestamp_granularities=["segment", "word"]
                )

            return transcript.model_dump() if hasattr(transcript, 'model_dump') else transcript

        except Exception as e:
            print(f"  Error transcribing: {e}")
            return None


# Segment creation utilities
def format_timestamp(start_time: float, end_time: float) -> str:
    """Format timestamp as [MM:SS-MM:SS]."""
    start_min = int(start_time // 60)
    start_sec = int(start_time % 60)
    end_min = int(end_time // 60)
    end_sec = int(end_time % 60)
    return f"[{start_min:02d}:{start_sec:02d}-{end_min:02d}:{end_sec:02d}]"


def create_segment_metadata(
    channel_name: str,
    video_title: str,
    video_id: str,
    start_time: float,
    end_time: float,
    language: str = "en"
) -> str:
    """Create metadata JSON string for a segment."""
    metadata = {
        'channel_name': channel_name,
        'video_title': video_title,
        'youtube_id': video_id,
        'start_time': start_time,
        'end_time': end_time,
        'duration': end_time - start_time,
        'segment_type': 'transcript_segment',
        'source': 'youtube_video',
        'language': language,
        'timestamp': format_timestamp(start_time, end_time)
    }
    return json.dumps(metadata)


def create_segments_from_transcript(
    transcript_data: Dict,
    channel_name: str
) -> List[TranscriptSegment]:
    """Break transcript into searchable segments with timestamps."""
    segments = []

    transcript = transcript_data.get('transcript', {})
    raw_segments = transcript.get('segments', [])
    video_title = transcript_data.get('title', 'Unknown')
    video_id = transcript_data.get('video_id', '')
    language = transcript.get('language', 'en')

    for segment in raw_segments:
        start_time = segment.get('start', 0)
        end_time = segment.get('end', 0)
        text = segment.get('text', '').strip()

        if not text:
            continue

        # Create segment text with timestamp
        timestamp = format_timestamp(start_time, end_time)
        segment_text = f"{timestamp} {text}"

        # Create metadata
        metadata_str = create_segment_metadata(
            channel_name=channel_name,
            video_title=video_title,
            video_id=video_id,
            start_time=start_time,
            end_time=end_time,
            language=language
        )

        segments.append(TranscriptSegment(
            text=segment_text,
            metadata=metadata_str
        ))

    return segments


# RAG integration utilities
def add_segment_to_rag(segment: TranscriptSegment, rag_api_url: str) -> bool:
    """Add a segment to the RAG system via API."""
    try:
        response = requests.post(
            f"{rag_api_url}/api/add-document",
            json=segment.dict(),
            timeout=30
        )
        response.raise_for_status()
        return True
    except Exception as e:
        print(f"    Error adding segment: {e}")
        return False


def process_transcript_file(
    transcript_file: Path,
    rag_api_url: str
) -> int:
    """Process a single transcript file."""
    print(f"\nProcessing: {transcript_file}")

    try:
        with open(transcript_file, 'r', encoding='utf-8') as f:
            data = json.load(f)

        # Extract channel name from path
        channel_name = transcript_file.parent.parent.name.replace("_", " ")

        # Create segments
        segments = create_segments_from_transcript(data, channel_name)
        print(f"  Created {len(segments)} segments")

        # Add to RAG
        success_count = 0
        for segment in segments:
            if add_segment_to_rag(segment, rag_api_url):
                success_count += 1

        print(f"  Added {success_count}/{len(segments)} segments to RAG")
        return success_count

    except Exception as e:
        print(f"  Error processing transcript: {e}")
        return 0


# Main processing workflows
def process_all_transcripts(
    output_dir: Path,
    rag_api_url: str
) -> IntegrationSummary:
    """Process all transcript files."""
    print("\n" + "="*80)
    print("ADDING TRANSCRIPTS TO RAG SYSTEM")
    print("="*80)

    transcript_files = find_transcript_files(output_dir)
    print(f"Found {len(transcript_files)} transcript files")

    total_segments = 0

    for idx, transcript_file in enumerate(transcript_files, 1):
        print(f"\n[{idx}/{len(transcript_files)}]")
        count = process_transcript_file(transcript_file, rag_api_url)
        total_segments += count

    summary = IntegrationSummary(
        total_transcripts=len(transcript_files),
        total_segments_added=total_segments
    )

    print(f"\n{'='*80}")
    print("INTEGRATION COMPLETE")
    print(f"{'='*80}")
    print(f"Transcripts processed: {summary.total_transcripts}")
    print(f"Segments added to RAG: {summary.total_segments_added}")

    return summary


def process_unprocessed_audio_files(
    output_dir: Path,
    openai_api_key: str,
    max_chunk_duration: int
) -> int:
    """Process unprocessed audio files."""
    print("\n" + "="*80)
    print("PROCESSING AUDIO FILES")
    print("="*80)

    openai_client = create_openai_client(openai_api_key)
    m4a_files = find_unprocessed_audio_files(output_dir)
    print(f"Found {len(m4a_files)} unprocessed audio files")

    processed = 0

    for idx, audio_file in enumerate(m4a_files, 1):
        print(f"\n[{idx}/{len(m4a_files)}] {audio_file.name}")

        transcript = transcribe_audio_file(audio_file, openai_client, max_chunk_duration)
        if transcript:
            # Save transcript
            transcripts_dir = audio_file.parent / "transcripts"
            transcripts_dir.mkdir(exist_ok=True)

            transcript_file = transcripts_dir / f"{audio_file.stem}_transcript.json"

            with open(transcript_file, 'w', encoding='utf-8') as f:
                json.dump({
                    'video_id': audio_file.stem,
                    'title': audio_file.stem,
                    'url': f"https://youtube.com/watch?v={audio_file.stem}",
                    'duration': transcript.get('duration', 0),
                    'transcript': transcript
                }, f, indent=2)

            print(f"  Saved transcript to {transcript_file}")
            processed += 1

            # Clean up audio file
            audio_file.unlink()
            print(f"  Deleted audio file")

    return processed


def main() -> None:
    """Main entry point."""
    if not OPENAI_API_KEY:
        print("Error: OPENAI_API_KEY not set in environment variables")
        return

    # Process existing transcripts
    process_all_transcripts(OUTPUT_DIR, RAG_API_URL)

    # Optionally process any m4a files found
    # process_unprocessed_audio_files(OUTPUT_DIR, OPENAI_API_KEY, MAX_CHUNK_DURATION)


if __name__ == "__main__":
    main()
