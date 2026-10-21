import sys
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import asyncio
from src.extractors.unified_resolver import UnifiedAudioResolver

async def main():
    resolver = UnifiedAudioResolver()
    
    # Test post 42
    print("Testing Telegram post #42...")
    res42 = await resolver.resolve_telegram("https://t.me/kMDHMUNcmJYwZTU0/42")
    safe_title42 = res42[0].title.encode('ascii', errors='replace').decode('ascii')
    print(f"Track 42: title='{safe_title42}' | stream={res42[0].stream_url[:60]}...")
    assert "e981e7a976" in res42[0].stream_url, "Post 42 did not get post 42's video!"

    # Test post 40
    print("\nTesting Telegram post #40...")
    res40 = await resolver.resolve_telegram("https://t.me/kMDHMUNcmJYwZTU0/40")
    safe_title40 = res40[0].title.encode('ascii', errors='replace').decode('ascii')
    print(f"Track 40: title='{safe_title40}' | stream={res40[0].stream_url[:60]}...")
    assert "f07ab5e851" in res40[0].stream_url, "Post 40 did not get post 40's video!"

    # Test post 38
    print("\nTesting Telegram post #38...")
    res38 = await resolver.resolve_telegram("https://t.me/kMDHMUNcmJYwZTU0/38")
    safe_title38 = res38[0].title.encode('ascii', errors='replace').decode('ascii')
    print(f"Track 38: title='{safe_title38}' | stream={res38[0].stream_url[:60]}...")
    assert "61bd3c824c" in res38[0].stream_url, "Post 38 did not get post 38's video!"

    # Test non-media post 41
    print("\nTesting Telegram post #41 (non-media post)...")
    try:
        await resolver.resolve_telegram("https://t.me/kMDHMUNcmJYwZTU0/41")
        print("ERROR: Post 41 should have failed as non-media!")
        assert False
    except ValueError as e:
        safe_e = str(e).encode('ascii', errors='replace').decode('ascii')
        print(f"Success! Correctly caught non-media post: {safe_e}")

    print("\n[ALL TESTS PASSED SUCCESSFULLY!]")

if __name__ == "__main__":
    asyncio.run(main())
