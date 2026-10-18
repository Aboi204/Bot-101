import asyncio
import os
import subprocess
import sys
from pathlib import Path

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.extractors.unified_resolver import UnifiedAudioResolver
from src.utils.logger import log, record_error_trace

# Detect ffmpeg path
FFMPEG_CMD = "ffmpeg"
winget_ffmpeg = Path(r"C:\Users\ISLAM\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.2-full_build\bin\ffmpeg.exe")
if winget_ffmpeg.exists():
    FFMPEG_CMD = str(winget_ffmpeg)

TEST_SOURCES = {
    "YouTube": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "SoundCloud": "https://soundcloud.com/nigeldelviero/chill-study-beats-lofi-hip-hop-mix-2018",
    "Facebook": "https://www.facebook.com/facebook/videos/10153231379946729/",
    "Telegram": "https://t.me/europa_press/613",
    "Google Drive": "https://drive.google.com/file/d/0ByeS4oOUV-49Zzh4R1J6R09zazQ/edit?pli=1"
}

def test_ffmpeg_decode(stream_url: str, source_name: str) -> bool:
    """Runs a 5-second headless ffmpeg decode test."""
    print(f"[*] Testing 5-second FFmpeg audio decode for {source_name}...")
    cmd = [
        FFMPEG_CMD,
        "-reconnect", "1",
        "-reconnect_streamed", "1",
        "-reconnect_delay_max", "5",
        "-nostdin",
        "-i", stream_url,
        "-t", "5",
        "-f", "null",
        "-"
    ]

    try:
        proc = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, timeout=25)
        if proc.returncode == 0:
            print(f"[PASS] {source_name}: FFmpeg decoded 5 seconds of audio successfully.")
            return True
        else:
            stderr_snippet = proc.stderr[-400:] if proc.stderr else "Unknown error"
            print(f"[FAIL] {source_name}: FFmpeg exited with code {proc.returncode}.\nStderr: {stderr_snippet}")
            return False
    except subprocess.TimeoutExpired:
        print(f"[FAIL] {source_name}: FFmpeg decode timed out after 25s.")
        return False
    except Exception as e:
        print(f"[FAIL] {source_name}: FFmpeg execution error: {e}")
        return False

async def verify_source(resolver: UnifiedAudioResolver, source_name: str, url: str) -> bool:
    print(f"\n==================================================")
    print(f"Verifying Source: {source_name}")
    print(f"Target URL: {url}")
    print(f"==================================================")

    try:
        tracks = await resolver.resolve(url)
        if not tracks:
            print(f"[FAIL] {source_name}: No tracks extracted.")
            return False

        track = tracks[0]
        safe_title = track.title.encode("ascii", errors="replace").decode("ascii")
        safe_uploader = track.uploader.encode("ascii", errors="replace").decode("ascii")
        print(f"[INFO] Title: {safe_title}")
        print(f"[INFO] Uploader: {safe_uploader}")
        print(f"[INFO] Stream URL: {track.stream_url[:80]}...")

        # Test FFmpeg decode
        decode_ok = test_ffmpeg_decode(track.stream_url, source_name)

        # Cleanup if local temporary file
        if track.is_local_file and track.local_file_path and os.path.exists(track.local_file_path):
            os.remove(track.local_file_path)
            print(f"[CLEANUP] Deleted temporary file: {track.local_file_path}")

        return decode_ok

    except Exception as e:
        print(f"[FAIL] {source_name}: Resolution failed with exception: {e}")
        record_error_trace(
            trace_id=f"TRC-TEST-{source_name.upper()}",
            exception=e,
            source_platform=source_name.lower(),
            input_url=url
        )
        return False

async def main():
    resolver = UnifiedAudioResolver()
    results = {}

    for name, url in TEST_SOURCES.items():
        results[name] = await verify_source(resolver, name, url)

    print("\n\n==================================================")
    print("FINAL 5-SOURCE VERIFICATION SUMMARY")
    print("==================================================")
    all_passed = True
    for name, passed in results.items():
        status = "PASS [OK]" if passed else "FAIL [X]"
        print(f"{name:<15}: {status}")
        if not passed:
            all_passed = False

    print("==================================================")
    if all_passed:
        print("ALL 5 SOURCES VERIFIED AND STREAMING OPERATIONAL!")
        sys.exit(0)
    else:
        print("SOME SOURCES FAILED. CHECK logs/error_traces.json FOR DIAGNOSIS.")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())
