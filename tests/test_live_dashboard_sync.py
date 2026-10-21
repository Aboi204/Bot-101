import sys
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import asyncio
from unittest.mock import AsyncMock, MagicMock
import discord

from src.extractors.unified_resolver import ResolvedTrack
from src.utils.voice_manager import GuildVoiceManager, LoopMode

async def test_dashboard_sync():
    print("Testing Live Dashboard synchronization and duplicate message prevention...")

    mock_bot = MagicMock()
    mock_guild = MagicMock()
    mock_guild.id = 123456
    mock_resolver = MagicMock()

    manager = GuildVoiceManager(mock_bot, mock_guild, mock_resolver)

    # Setup mock text channel and message
    mock_message = AsyncMock()
    mock_message.edit = AsyncMock()

    mock_channel = AsyncMock()
    mock_channel.send = AsyncMock(return_value=mock_message)
    manager.text_channel = mock_channel

    track1 = ResolvedTrack(
        title="Test Song 1",
        webpage_url="https://youtube.com/watch?v=111",
        stream_url="https://stream.audio/1",
        duration=120,
        thumbnail=None,
        uploader="Artist 1",
        source_platform="youtube",
        trace_id="TRC-T1"
    )

    track2 = ResolvedTrack(
        title="Test Song 2",
        webpage_url="https://youtube.com/watch?v=222",
        stream_url="https://stream.audio/2",
        duration=200,
        thumbnail=None,
        uploader="Artist 2",
        source_platform="youtube",
        trace_id="TRC-T2"
    )

    manager.current = track1

    # 1. First track starts -> should call text_channel.send
    await manager.update_now_playing_message()
    assert mock_channel.send.call_count == 1, f"Expected 1 send, got {mock_channel.send.call_count}"
    assert manager.current_message == mock_message
    print("[PASS] Initial playback sent single dashboard message.")

    # 2. User clicks Replay -> should call mock_message.edit, NEVER mock_channel.send again
    replay_success = manager.replay_current()
    assert replay_success is True
    assert manager.is_replaying is True
    assert manager.is_recovering is False

    await manager.update_now_playing_message()
    assert mock_channel.send.call_count == 1, "Duplicate message sent during replay! Expected send.call_count == 1"
    assert mock_message.edit.call_count == 1, f"Expected message.edit called 1 time, got {mock_message.edit.call_count}"
    print("[PASS] Replay updated message in-place without duplicate message!")

    # 3. Track 2 plays (transition / skip) -> should edit mock_message in-place
    manager.current = track2
    await manager.update_now_playing_message()
    assert mock_channel.send.call_count == 1, "Duplicate message sent during track transition!"
    assert mock_message.edit.call_count == 2, f"Expected message.edit called 2 times, got {mock_message.edit.call_count}"
    print("[PASS] Track transition updated message in-place without duplicate message!")

    # 4. Playback stopped / queue empty -> should edit mock_message with disabled buttons
    manager.current = None
    await manager.update_now_playing_message()
    assert mock_channel.send.call_count == 1, "Duplicate message sent on playback stop!"
    assert mock_message.edit.call_count == 3
    # Check that children buttons are disabled
    assert all(child.disabled for child in manager.current_view.children), "Buttons not disabled on playback stop!"
    print("[PASS] Playback stop disabled all buttons and updated message in-place!")

    # 5. Recovery if user deleted message (NotFound exception)
    mock_message.edit.side_effect = discord.NotFound(MagicMock(), "Unknown Message")
    manager.current = track1
    await manager.update_now_playing_message()
    assert mock_channel.send.call_count == 2, "Failed to send fresh message after previous message was deleted!"
    print("[PASS] Clean fallback to fresh message when existing message was deleted.")

    print("\n[ALL DASHBOARD SYNC TESTS PASSED!]")

if __name__ == "__main__":
    asyncio.run(test_dashboard_sync())
