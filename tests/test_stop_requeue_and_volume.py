import sys
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import asyncio
from unittest.mock import MagicMock
import discord

from src.extractors.unified_resolver import ResolvedTrack, UnifiedAudioResolver
from src.utils.voice_manager import GuildVoiceManager, LoopMode, PrebufferedAudioSource
from src.utils.ui_controls import build_now_playing_embed, MusicControlView

def test_embed_no_progress_bar():
    print("Testing embed formatting (no progress bar)...")
    mock_manager = MagicMock()
    mock_manager.is_paused = False
    mock_manager.volume = 1.0
    mock_manager.loop_mode = LoopMode.OFF
    mock_manager.queue = []
    mock_manager.current = ResolvedTrack(
        title="Test Song Title",
        webpage_url="https://youtube.com/watch?v=123",
        stream_url="https://test.stream/audio",
        duration=240,
        thumbnail="https://test.thumb/img.jpg",
        uploader="Test Artist",
        source_platform="youtube",
        trace_id="TRC-TEST"
    )

    embed = build_now_playing_embed(mock_manager)
    desc = embed.description
    print(f"Embed description: {desc}")
    assert "─🔘─" not in desc, "Progress bar still found in embed description!"
    assert "🔘" not in desc, "🔘 emoji still found in embed description!"
    assert "[Test Song Title](https://youtube.com/watch?v=123)" in desc
    print("[OK] Progress bar completely removed!")

def test_view_buttons():
    print("\nTesting interactive view buttons...")
    mock_manager = MagicMock()
    mock_manager.is_paused = False
    mock_manager.volume = 1.0
    mock_manager.loop_mode = LoopMode.OFF
    mock_manager.history = []
    mock_manager.queue = []
    mock_manager.current = None

    view = MusicControlView(mock_manager)
    button_custom_ids = [child.custom_id for child in view.children if isinstance(child, discord.ui.Button)]
    print(f"Buttons found: {button_custom_ids}")
    expected = [
        "btn_prev", "btn_pause_resume", "btn_next", "btn_replay", "btn_stop",
        "btn_vol_down", "btn_vol_up", "btn_shuffle", "btn_loop", "btn_queue"
    ]
    for exp in expected:
        assert exp in button_custom_ids, f"Missing button: {exp}"
    print("[OK] All 10 interactive control buttons present!")

def test_manager_methods():
    print("\nTesting manager mix & volume methods...")
    mock_bot = MagicMock()
    mock_guild = MagicMock()
    mock_resolver = MagicMock()
    mgr = GuildVoiceManager(mock_bot, mock_guild, mock_resolver)
    
    # Test volume adjustment
    mgr.set_volume(100)
    assert mgr.volume == 1.0
    new_vol = mgr.adjust_volume(15)
    assert new_vol == 115
    assert round(mgr.volume, 2) == 1.15
    new_vol = mgr.adjust_volume(-30)
    assert new_vol == 85
    assert round(mgr.volume, 2) == 0.85

    # Test loop cycling
    assert mgr.loop_mode == LoopMode.OFF
    assert mgr.cycle_loop_mode() == LoopMode.TRACK
    assert mgr.cycle_loop_mode() == LoopMode.QUEUE
    assert mgr.cycle_loop_mode() == LoopMode.OFF

    # Test shuffle
    t1 = ResolvedTrack("S1", "u1", "s1", 100, "", "", "yt", "t1")
    t2 = ResolvedTrack("S2", "u2", "s2", 100, "", "", "yt", "t2")
    t3 = ResolvedTrack("S3", "u3", "s3", 100, "", "", "yt", "t3")
    mgr.queue.extend([t1, t2, t3])
    shuffled_count = mgr.shuffle_queue()
    assert shuffled_count == 3
    print("[OK] Manager methods test passed!")

if __name__ == "__main__":
    test_embed_no_progress_bar()
    test_view_buttons()
    test_manager_methods()
    print("\n[ALL TESTS PASSED SUCCESSFULLY!]")
