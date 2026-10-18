import asyncio
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.extractors.unified_resolver import UnifiedAudioResolver

async def test_telegram_sources():
    resolver = UnifiedAudioResolver()

    # Test 1: User's private/invite channel video post 42
    url_42 = "https://t.me/kMDHMUNcmJYwZTU0/42"
    print(f"\n[1] Testing Telegram Post 42: {url_42}")
    tracks_42 = await resolver.resolve(url_42)
    assert len(tracks_42) > 0, "Failed to resolve post 42"
    t42 = tracks_42[0]
    print(f"    Title: {t42.title}")
    print(f"    Author: {t42.uploader}")
    print(f"    Duration: {t42.formatted_duration}")
    print(f"    Stream URL: {t42.stream_url[:70]}...")
    assert "telesco.pe" in t42.stream_url or "t.me" in t42.stream_url
    print("    [PASS] Post 42 resolved with high-quality stream URL!")

    # Test 2: Channel with + prefix
    url_plus = "https://t.me/+kMDHMUNcmJYwZTU0/42"
    print(f"\n[2] Testing Telegram URL with + prefix: {url_plus}")
    tracks_plus = await resolver.resolve(url_plus)
    assert len(tracks_plus) > 0, "Failed to resolve plus URL"
    print(f"    Title: {tracks_plus[0].title}")
    print("    [PASS] + prefix handled correctly!")

    # Test 3: Standard public channel post
    url_pub = "https://t.me/El_minshawy/189"
    print(f"\n[3] Testing Standard Public Channel Post: {url_pub}")
    tracks_pub = await resolver.resolve(url_pub)
    assert len(tracks_pub) > 0, "Failed to resolve public audio"
    print(f"    Title: {tracks_pub[0].title[:50]}")
    print("    [PASS] Public channel audio resolved!")

    # Test 4: Post 41 (Sheikh Muhammad Imran)
    url_41 = "https://t.me/kMDHMUNcmJYwZTU0/41"
    print(f"\n[4] Testing Telegram Post 41: {url_41}")
    tracks_41 = await resolver.resolve(url_41)
    assert len(tracks_41) > 0, "Failed to resolve post 41"
    t41 = tracks_41[0]
    print(f"    Title: {t41.title}")
    print(f"    Author: {t41.uploader}")
    print(f"    Stream URL: {t41.stream_url[:70]}...")
    assert "telesco.pe" in t41.stream_url or "t.me" in t41.stream_url
    print("    [PASS] Post 41 resolved and streams successfully!")

    print("\n[ALL PASS] Telegram resolution verified across all formats!")

if __name__ == "__main__":
    asyncio.run(test_telegram_sources())
