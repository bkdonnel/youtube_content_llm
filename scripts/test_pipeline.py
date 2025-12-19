#!/usr/bin/env python3
"""
Simple Test Pipeline - Phase 1
Tests all components locally before deploying to AWS
"""

import os
import sys
from datetime import datetime
from pathlib import Path
import yt_dlp
from openai import OpenAI
import snowflake.connector
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()

# Configuration from .env
SNOWFLAKE_ACCOUNT = os.getenv('SNOWFLAKE_ACCOUNT')
SNOWFLAKE_USER = os.getenv('SNOWFLAKE_USER')
SNOWFLAKE_PASSWORD = os.getenv('SNOWFLAKE_PASSWORD')
SNOWFLAKE_WAREHOUSE = os.getenv('SNOWFLAKE_WAREHOUSE', 'COMPUTE_WH')
SNOWFLAKE_DATABASE = os.getenv('SNOWFLAKE_DATABASE', 'MUSIC_PRODUCTION_CONTENT')
SNOWFLAKE_SCHEMA = os.getenv('SNOWFLAKE_SCHEMA', 'RAW')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')
ZEN_WORLD_CHANNEL_ID = os.getenv('ZEN_WORLD_CHANNEL_ID')

# Initialize OpenAI client
openai_client = OpenAI(api_key=OPENAI_API_KEY)

# Create output directory
OUTPUT_DIR = Path("test_output")
OUTPUT_DIR.mkdir(exist_ok=True)


def test_snowflake_connection():
    """Test 1: Verify Snowflake connection works"""
    print("\n" + "="*60)
    print("TEST 1: Snowflake Connection")
    print("="*60)
    
    try:
        conn = snowflake.connector.connect(
            user=SNOWFLAKE_USER,
            password=SNOWFLAKE_PASSWORD,
            account=SNOWFLAKE_ACCOUNT,
            warehouse=SNOWFLAKE_WAREHOUSE,
            database=SNOWFLAKE_DATABASE,
            schema=SNOWFLAKE_SCHEMA
        )
        
        cursor = conn.cursor()
        
        # Test query
        cursor.execute("SELECT COUNT(*) FROM CREATORS")
        count = cursor.fetchone()[0]
        print(f"Connected to Snowflake successfully!")
        print(f"   Found {count} creator(s) in database")
        
        # Show creators
        cursor.execute("SELECT creator_id, creator_name FROM CREATORS")
        for row in cursor.fetchall():
            print(f"   - {row[1]} (ID: {row[0]})")
        
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"Snowflake connection failed: {e}")
        return False


def test_youtube_download(channel_url=None, max_videos=5, min_duration=60):
    """Test 2: Download audio from recent YouTube videos (excluding shorts)"""
    print("\n" + "="*60)
    print("TEST 2: YouTube Download (5 Most Recent Videos)")
    print("="*60)

    if not channel_url:
        # Auto-populate from .env file
        if ZEN_WORLD_CHANNEL_ID:
            channel_url = f"https://www.youtube.com/channel/{ZEN_WORLD_CHANNEL_ID}/videos"
            print(f"Using channel ID from .env: {ZEN_WORLD_CHANNEL_ID}")
        else:
            print("⏭️  Skipped (ZEN_WORLD_CHANNEL_ID not set in .env)")
            return []

    print(f"Fetching recent videos from channel...")
    print(f"   Excluding videos shorter than {min_duration}s (shorts)")
    print(f"   Downloading up to {max_videos} videos")

    # First, extract video list without downloading
    ydl_opts_info = {
        'quiet': True,
        'extract_flat': True,
        'playlistend': 50,  # Get more videos to filter from
    }

    try:
        videos_downloaded = []

        # Get channel videos
        with yt_dlp.YoutubeDL(ydl_opts_info) as ydl:
            # Extract channel/playlist info
            playlist_info = ydl.extract_info(channel_url, download=False)

            if 'entries' not in playlist_info:
                print("Could not find videos in channel")
                return []

            # Filter and collect video URLs
            valid_videos = []
            for entry in playlist_info['entries']:
                if entry is None:
                    continue

                video_url = f"https://www.youtube.com/watch?v={entry['id']}"
                valid_videos.append(video_url)

                if len(valid_videos) >= max_videos * 3:  # Get extra to filter
                    break

        # Now download and filter videos
        ydl_opts_download = {
            'format': 'bestaudio[ext=m4a]/bestaudio',
            'outtmpl': str(OUTPUT_DIR / '%(id)s.%(ext)s'),
            'quiet': False,
        }

        downloaded_count = 0
        for video_url in valid_videos:
            if downloaded_count >= max_videos:
                break

            try:
                with yt_dlp.YoutubeDL(ydl_opts_download) as ydl:
                    info = ydl.extract_info(video_url, download=False)

                    duration = info.get('duration', 0)

                    # Skip shorts (videos shorter than min_duration)
                    if duration < min_duration:
                        print(f"\nSkipping short video: {info['title']}")
                        print(f"   Duration: {duration}s (< {min_duration}s)")
                        continue

                    # Download the video
                    print(f"\nDownloading video {downloaded_count + 1}/{max_videos}...")
                    info = ydl.extract_info(video_url, download=True)

                    video_id = info['id']
                    title = info['title']

                    print(f"   Title: {title}")
                    print(f"   Duration: {duration}s ({duration/60:.1f} minutes)")
                    print(f"   Video ID: {video_id}")

                    # Find the downloaded file
                    audio_file = None
                    for ext in ['m4a', 'mp3', 'webm']:
                        file_path = OUTPUT_DIR / f"{video_id}.{ext}"
                        if file_path.exists():
                            audio_file = str(file_path)
                            print(f"   File: {file_path}")
                            break

                    if audio_file:
                        videos_downloaded.append((audio_file, info))
                        downloaded_count += 1

            except Exception as e:
                print(f"   Failed to download {video_url}: {e}")
                continue

        print(f"\nSuccessfully downloaded {len(videos_downloaded)} video(s)")
        return videos_downloaded

    except Exception as e:
        print(f"Download failed: {e}")
        return []


def test_openai_transcription(audio_file_path):
    """Test 3: Transcribe audio with OpenAI Whisper"""
    print("\n" + "="*60)
    print("TEST 3: OpenAI Transcription")
    print("="*60)

    if not audio_file_path:
        print("No audio file to transcribe (skipped)")
        return None

    print(f"Transcribing: {audio_file_path}")
    print("   This may take a few minutes...")

    try:
        with open(audio_file_path, 'rb') as audio_file:
            transcript = openai_client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                response_format="verbose_json",
                timestamp_granularities=["segment"]
            )

        # Convert to dict if needed
        transcript_dict = transcript.model_dump() if hasattr(transcript, 'model_dump') else transcript

        print(f"Transcription complete!")
        print(f"   Language: {transcript_dict.get('language', 'unknown')}")
        print(f"   Duration: {transcript_dict.get('duration', 0):.1f}s")
        print(f"   Segments: {len(transcript_dict.get('segments', []))}")

        # Show first few segments
        segments = transcript_dict.get('segments', [])
        if segments:
            print("\n   First 3 segments:")
            for i, seg in enumerate(segments[:3]):
                start = seg.get('start', 0)
                text = seg.get('text', '').strip()
                print(f"   [{start:.1f}s] {text[:80]}...")

        return transcript_dict

    except Exception as e:
        print(f"Transcription failed: {e}")
        return None


def test_snowflake_insert(video_info, transcript_data):
    """Test 4: Insert data into Snowflake"""
    print("\n" + "="*60)
    print("TEST 4: Insert Data to Snowflake")
    print("="*60)
    
    if not video_info or not transcript_data:
        print("⏭️  No data to insert (skipped)")
        return False
    
    try:
        conn = snowflake.connector.connect(
            user=SNOWFLAKE_USER,
            password=SNOWFLAKE_PASSWORD,
            account=SNOWFLAKE_ACCOUNT,
            warehouse=SNOWFLAKE_WAREHOUSE,
            database=SNOWFLAKE_DATABASE,
            schema=SNOWFLAKE_SCHEMA
        )
        
        cursor = conn.cursor()
        
        video_id = video_info['id']
        
        # Insert video
        print("   Inserting video record...")
        cursor.execute("""
            INSERT INTO VIDEOS (
                video_id, creator_id, title, description, video_url,
                thumbnail_url, upload_date, duration_seconds,
                processing_status, processed_at
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s, %s, CURRENT_TIMESTAMP()
            )
        """, (
            video_id,
            'zen_world',
            video_info['title'],
            video_info.get('description', ''),
            video_info['webpage_url'],
            video_info.get('thumbnail', ''),
            datetime.strptime(video_info.get('upload_date', '20240101'), '%Y%m%d').date(),
            video_info.get('duration', 0),
            'completed'
        ))
        
        # Insert transcript
        print("   Inserting transcript...")
        transcript_id = f"{video_id}_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        full_text = transcript_data.get('text', '')
        
        cursor.execute("""
            INSERT INTO TRANSCRIPTS (
                transcript_id, video_id, full_text, language,
                duration_seconds, word_count, generated_at, model_version
            ) VALUES (
                %s, %s, %s, %s, %s, %s, %s, %s
            )
        """, (
            transcript_id,
            video_id,
            full_text,
            transcript_data.get('language', 'en'),
            transcript_data.get('duration', 0),
            len(full_text.split()),
            datetime.now(),
            'whisper-1'
        ))
        
        # Insert segments
        segments = transcript_data.get('segments', [])
        print(f"   Inserting {len(segments)} segments...")
        
        for i, segment in enumerate(segments):
            segment_id = f"{transcript_id}_seg_{i}"
            
            cursor.execute("""
                INSERT INTO TRANSCRIPT_SEGMENTS (
                    segment_id, transcript_id, video_id, segment_index,
                    start_time_seconds, end_time_seconds, text, word_count
                ) VALUES (
                    %s, %s, %s, %s, %s, %s, %s, %s
                )
            """, (
                segment_id,
                transcript_id,
                video_id,
                i,
                segment.get('start', 0),
                segment.get('end', 0),
                segment.get('text', '').strip(),
                len(segment.get('text', '').split())
            ))
        
        conn.commit()
        
        print("Data inserted successfully!")
        print(f"   Video ID: {video_id}")
        print(f"   Transcript ID: {transcript_id}")
        print(f"   Segments: {len(segments)}")
        
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"Insert failed: {e}")
        return False


def test_snowflake_query():
    """Test 5: Query the data we just inserted"""
    print("\n" + "="*60)
    print("TEST 5: Query Snowflake Data")
    print("="*60)
    
    try:
        conn = snowflake.connector.connect(
            user=SNOWFLAKE_USER,
            password=SNOWFLAKE_PASSWORD,
            account=SNOWFLAKE_ACCOUNT,
            warehouse=SNOWFLAKE_WAREHOUSE,
            database=SNOWFLAKE_DATABASE,
            schema='ANALYTICS'
        )
        
        cursor = conn.cursor()
        
        # Test VIDEO_SEARCH view
        print("   Testing VIDEO_SEARCH view...")
        cursor.execute("SELECT COUNT(*) FROM VIDEO_SEARCH")
        count = cursor.fetchone()[0]
        print(f"   Found {count} completed video(s)")
        
        # Test SEGMENT_SEARCH view
        print("   Testing SEGMENT_SEARCH view...")
        cursor.execute("SELECT COUNT(*) FROM SEGMENT_SEARCH")
        count = cursor.fetchone()[0]
        print(f"   Found {count} searchable segment(s)")
        
        # Try a search
        search_term = "the"  # Common word that should exist
        cursor.execute(f"""
            SELECT video_title, segment_text
            FROM SEGMENT_SEARCH
            WHERE LOWER(segment_text) LIKE '%{search_term}%'
            LIMIT 3
        """)
        
        results = cursor.fetchall()
        if results:
            print(f"\n   Sample search results for '{search_term}':")
            for video_title, segment_text in results:
                print(f"   - {segment_text[:100]}...")
        
        cursor.close()
        conn.close()
        
        return True
        
    except Exception as e:
        print(f"Query failed: {e}")
        return False


def main():
    """Run all tests"""
    print("\n" + "🎵"*30)
    print("MUSIC PRODUCTION PIPELINE - LOCAL TEST SUITE")
    print("🎵"*30)
    
    # Check environment variables
    print("\nChecking configuration...")
    required_vars = [
        'SNOWFLAKE_ACCOUNT',
        'SNOWFLAKE_USER',
        'SNOWFLAKE_PASSWORD',
        'OPENAI_API_KEY'
    ]
    
    missing = [var for var in required_vars if not os.getenv(var)]
    if missing:
        print(f"Missing environment variables: {', '.join(missing)}")
        print("   Please check your .env file")
        sys.exit(1)
    
    print("All environment variables set")
    
    # Run tests
    results = {}
    
    # Test 1: Snowflake connection
    results['snowflake_connection'] = test_snowflake_connection()
    
    if not results['snowflake_connection']:
        print("\n⚠️  Snowflake connection failed. Fix this before continuing.")
        return
    
    # Test 2: YouTube download (optional)
    videos_downloaded = test_youtube_download()
    results['youtube_download'] = len(videos_downloaded) > 0

    # Test 3 & 4: Process each downloaded video
    if videos_downloaded:
        print(f"\n{'='*60}")
        print(f"Processing {len(videos_downloaded)} video(s)")
        print(f"{'='*60}")

        successful_inserts = 0

        for idx, (audio_file, video_info) in enumerate(videos_downloaded, 1):
            print(f"\n--- Processing video {idx}/{len(videos_downloaded)} ---")

            # Test 3: Transcribe
            transcript_data = test_openai_transcription(audio_file)
            if transcript_data:
                results['openai_transcription'] = True

                # Test 4: Insert to Snowflake
                if test_snowflake_insert(video_info, transcript_data):
                    successful_inserts += 1

        results['snowflake_insert'] = successful_inserts > 0

        # Test 5: Query the data
        if successful_inserts > 0:
            results['snowflake_query'] = test_snowflake_query()
    else:
        results['openai_transcription'] = False
        results['snowflake_insert'] = False
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    for test_name, passed in results.items():
        status = "PASS" if passed else "FAIL"
        print(f"{status} - {test_name}")
    
    passed = sum(1 for v in results.values() if v)
    total = len(results)
    
    print(f"\nPassed: {passed}/{total}")
    
    if passed == total:
        print("\nAll tests passed! You're ready to build the Streamlit app.")
    elif results.get('snowflake_connection'):
        print("\nCore functionality works! You can start building the Streamlit app.")
        print("   (The full pipeline can be built once you test a complete video)")
    else:
        print("\n⚠️  Fix the failed tests before continuing")
    
    # Cleanup
    print("\n🧹 Cleanup:")
    if videos_downloaded:
        # Auto-cleanup test files
        print(f"   Deleting {len(videos_downloaded)} test audio file(s)...")
        for audio_file, _ in videos_downloaded:
            if os.path.exists(audio_file):
                os.remove(audio_file)
        print(f"   Deleted {len(videos_downloaded)} audio file(s)")


if __name__ == "__main__":
    main()