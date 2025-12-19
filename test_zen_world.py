#!/usr/bin/env python3
"""
Test script to download and transcribe just the most recent Zen World video
"""

import os
from pathlib import Path
from dotenv import load_dotenv

from youtube_transcript_downloader import (
    get_channel_videos,
    process_single_video,
    create_openai_client
)

# Load environment variables
load_dotenv()

# Configuration
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OUTPUT_DIR = Path(os.getenv("OUTPUT_DIR", "music_tutorials"))

# Zen World channel info
ZEN_WORLD = {
    "name": "Zen World",
    "url": "https://www.youtube.com/@ZenWorld",
    "description": "Tutorials on arrangement, sound design, tech house and techno"
}


def main():
    """Download and transcribe the most recent Zen World video."""
    if not OPENAI_API_KEY:
        print("Error: OPENAI_API_KEY not set in environment variables")
        return

    print("=" * 80)
    print("TESTING WITH ZEN WORLD - MOST RECENT VIDEO")
    print("=" * 80)

    # Create output directory
    creator_dir = OUTPUT_DIR / "Zen_World"
    creator_dir.mkdir(exist_ok=True, parents=True)

    # Get the most recent video (max_videos=1)
    print(f"\nFetching most recent video from: {ZEN_WORLD['url']}")
    videos = get_channel_videos(ZEN_WORLD['url'], max_videos=1)

    if not videos:
        print("No videos found!")
        return

    print(f"\nFound video: {videos[0].title}")
    print(f"URL: {videos[0].url}")

    # Create OpenAI client
    openai_client = create_openai_client(OPENAI_API_KEY)

    # Process the video
    print("\nProcessing video...")
    success = process_single_video(videos[0], creator_dir, openai_client)

    if success:
        print("\n" + "=" * 80)
        print("SUCCESS!")
        print("=" * 80)
        print(f"Transcript saved to: {creator_dir / 'transcripts'}")
    else:
        print("\n" + "=" * 80)
        print("FAILED")
        print("=" * 80)


if __name__ == "__main__":
    main()
