import asyncio
import os
import subprocess
import sys
import time
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.extractors.unified_resolver import UnifiedAudioResolver
from src.utils.voice_manager import get_ffmpeg_executable

async def test_facebook_url():
    user_url = "https://www.facebook.com/watch/?ref=saved&v=884001474643399"
    print(f"[*] Testing target user Facebook URL:\n    {user_url}\n")

    resolver = UnifiedAudioResolver()
    t0 = time.time()
    tracks = await resolver.resolve(user_url)
    resolve_time = time.time() - t0

    assert tracks, "No tracks returned!"
    track = tracks[0]
    print(f"[+] RESOLUTION SUCCESS in {resolve_time:.2f}s:")
    print(f"    Platform:  {track.source_platform.upper()} (Must be FACEBOOK)")
    assert track.source_platform == "facebook", f"Expected facebook, got {track.source_platform}!"
    print(f"    Title:     {track.title.encode('ascii', errors='replace').decode('ascii')}")
    print(f"    Webpage:   {track.webpage_url}")
    print(f"    Duration:  {track.formatted_duration}")
    print(f"    Stream:    {track.stream_url[:80]}...")
    print(f"    Is Local:  {track.is_local_file} (Must be False for Direct Streaming)")
    assert not track.is_local_file, "Track should be a direct network stream, not a local file!"

    # Test FFmpeg direct audio streaming decode (5 seconds)
    ffmpeg = get_ffmpeg_executable()
    cmd = [
        ffmpeg,
        "-reconnect", "1",
        "-reconnect_streamed", "1",
        "-reconnect_delay_max", "5",
        "-nostdin",
        "-user_agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "-i", track.stream_url,
        "-vn",
        "-t", "5",
        "-f", "null",
        "-"
    ]

    t1 = time.time()
    proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    stream_time = time.time() - t1

    assert proc.returncode == 0, f"FFmpeg failed with code {proc.returncode}: {proc.stderr[-300:]}"
    print(f"[+] DIRECT STREAMING TEST PASSED in {stream_time:.2f}s (FFmpeg code 0)")
    print("\n[VERIFIED] 100% operational HD direct Facebook streaming without downloading!")

if __name__ == "__main__":
    asyncio.run(test_facebook_url())
