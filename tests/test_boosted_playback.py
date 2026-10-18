import asyncio
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

import discord
from src.extractors.unified_resolver import UnifiedAudioResolver
from src.utils.voice_manager import GuildVoiceManager, get_ffmpeg_executable

async def verify_boosted_stream():
    resolver = UnifiedAudioResolver()
    ffmpeg_exe = get_ffmpeg_executable()

    test_urls = [
        ("YouTube", "https://www.youtube.com/watch?v=vU1-yqG9DEU"),
        ("Telegram", "https://t.me/kMDHMUNcmJYwZTU0/42")
    ]

    for platform, url in test_urls:
        print(f"\n[+] Resolving {platform} track...")
        tracks = await resolver.resolve(url)
        track = tracks[0]
        print(f"    Title: {track.title}")
        print(f"    Stream URL: {track.stream_url[:60]}...")

        # Initialize discord.FFmpegPCMAudio with boosted options
        before_opts = GuildVoiceManager.FFMPEG_OPTIONS['before_options']
        options = GuildVoiceManager.FFMPEG_OPTIONS['options']
        
        print(f"    Initializing discord.FFmpegPCMAudio with options: {options}")
        raw_source = discord.FFmpegPCMAudio(
            track.stream_url,
            executable=ffmpeg_exe,
            before_options=before_opts,
            options=options
        )
        audio_source = discord.PCMVolumeTransformer(raw_source, volume=1.0)

        # Read 5 frames (100ms) of boosted PCM audio
        frames_read = 0
        total_bytes = 0
        for _ in range(5):
            data = audio_source.read()
            if data:
                frames_read += 1
                total_bytes += len(data)

        audio_source.cleanup()
        assert frames_read > 0, f"No audio frames read for {platform}!"
        print(f"    [PASS] Successfully read {frames_read} boosted audio frames ({total_bytes} bytes) for {platform}!")

    print("\n[VERIFIED] Boosted audio streaming pipeline verified across platforms!")

if __name__ == "__main__":
    asyncio.run(verify_boosted_stream())
