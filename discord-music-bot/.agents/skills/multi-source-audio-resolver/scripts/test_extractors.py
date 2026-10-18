#!/usr/bin/env python3
"""
Test Extractors Script
Validates audio stream extraction across YouTube, SoundCloud, Spotify links, and text queries using yt-dlp.
"""

import argparse
import json
import os
import sys
import urllib.request

try:
    import yt_dlp
except ImportError:
    print("[ERROR] 'yt-dlp' is required. Install via: pip install yt-dlp")
    sys.exit(1)

def build_ydl(cookie_path: str = None):
    ydl_opts = {
        'format': 'bestaudio/best',
        'noplaylist': True,
        'quiet': True,
        'no_warnings': True,
        'default_search': 'ytsearch',
        'extract_flat': False,
    }
    if cookie_path and os.path.exists(cookie_path):
        ydl_opts['cookiefile'] = cookie_path
    return yt_dlp.YoutubeDL(ydl_opts)

def test_stream_url(stream_url: str) -> bool:
    """Sends a HEAD / partial GET request to test if the stream URL responds with 200/206."""
    try:
        req = urllib.request.Request(
            stream_url,
            headers={
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)',
                'Range': 'bytes=0-1024'
            }
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.status in (200, 206)
    except Exception as e:
        print(f"    [!] Stream connectivity test warning: {e}")
        return False

def resolve_target(target: str, cookie_path: str = None):
    print(f"[*] Testing target: '{target}'")
    ydl = build_ydl(cookie_path)

    try:
        info = ydl.extract_info(target, download=False)
        if not info:
            print("[FAIL] No information extracted.")
            return False

        if 'entries' in info:
            # Query was a search or playlist
            entries = list(info['entries'])
            if not entries:
                print("[FAIL] Empty search results.")
                return False
            item = entries[0]
        else:
            item = info

        title = item.get('title', 'Unknown')
        uploader = item.get('uploader', 'Unknown')
        duration = item.get('duration', 0)
        extractor = item.get('extractor', 'Unknown')
        stream_url = item.get('url', None)

        print("\n--- Extracted Metadata ---")
        print(f"Title:     {title}")
        print(f"Uploader:  {uploader}")
        print(f"Duration:  {duration} seconds")
        print(f"Extractor: {extractor}")
        print(f"Stream URL Available: {'YES' if stream_url else 'NO'}")

        if stream_url:
            print("[*] Probing audio stream URL...")
            can_connect = test_stream_url(stream_url)
            print(f"Audio Stream Reachable: {'SUCCESS' if can_connect else 'PARTIAL/FAILED'}")
            return can_connect

        return True

    except Exception as e:
        print(f"[FAIL] Extraction error: {e}")
        return False

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Test audio stream extraction for Discord bot")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--query", help="Text search query (e.g. 'lofi hip hop')")
    group.add_argument("--url", help="Direct URL (YouTube, SoundCloud, etc.)")
    parser.add_argument("--cookie-file", default="cookies.txt", help="Optional path to Netscape cookies.txt")
    args = parser.parse_args()

    target = args.url if args.url else f"ytsearch:{args.query}"
    cookie_path = args.cookie_file if os.path.exists(args.cookie_file) else None

    success = resolve_target(target, cookie_path)
    sys.exit(0 if success else 1)
