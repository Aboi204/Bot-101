import sys
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import asyncio
from unittest.mock import AsyncMock, MagicMock
import discord

from src.cogs.music import MusicCog
from src.extractors.unified_resolver import UnifiedAudioResolver

async def test_voice_restrictions():
    print("Testing Voice Channel Presence and Auto-Disconnect Restrictions...")

    mock_bot = MagicMock()
    mock_bot.user = MagicMock()
    mock_bot.user.id = 999999
    mock_bot.voice_clients = []

    cog = MusicCog(mock_bot)

    # 1. Test _ensure_voice when user is NOT in voice channel
    interaction_no_voice = MagicMock(spec=discord.Interaction)
    interaction_no_voice.user = MagicMock()
    interaction_no_voice.user.voice = None
    interaction_no_voice.response = MagicMock()
    interaction_no_voice.response.is_done.return_value = False
    interaction_no_voice.response.send_message = AsyncMock()

    vc_result = await cog._ensure_voice(interaction_no_voice)
    assert vc_result is None, "Bot connected even though user was NOT in voice channel!"
    assert interaction_no_voice.response.send_message.call_count == 1
    print("[PASS] Blocked bot from joining when user was not in voice channel.")

    # 2. Test _ensure_voice when user IS in voice channel
    mock_voice_channel = AsyncMock(spec=discord.VoiceChannel)
    mock_vc = MagicMock(spec=discord.VoiceClient)
    mock_vc.is_connected.return_value = True
    mock_vc.channel = mock_voice_channel
    mock_voice_channel.connect = AsyncMock(return_value=mock_vc)

    interaction_in_voice = MagicMock(spec=discord.Interaction)
    interaction_in_voice.user = MagicMock()
    interaction_in_voice.user.voice = MagicMock()
    interaction_in_voice.user.voice.channel = mock_voice_channel
    interaction_in_voice.guild = MagicMock()
    interaction_in_voice.guild.voice_client = None

    vc_result = await cog._ensure_voice(interaction_in_voice)
    assert vc_result == mock_vc
    assert mock_voice_channel.connect.call_count == 1
    print("[PASS] Bot successfully connected to user's voice channel when present.")

    # 3. Test on_voice_state_update when last member leaves
    mock_member = MagicMock(spec=discord.Member)
    mock_member.id = 12345  # Not the bot
    mock_member.bot = False
    mock_guild = MagicMock(spec=discord.Guild)
    mock_member.guild = mock_guild

    mock_vc.disconnect = AsyncMock()
    mock_guild.voice_client = mock_vc

    # Set channel members to only the bot
    bot_member = MagicMock()
    bot_member.bot = True
    mock_voice_channel.members = [bot_member]

    before_state = MagicMock(spec=discord.VoiceState)
    before_state.channel = mock_voice_channel

    after_state = MagicMock(spec=discord.VoiceState)
    after_state.channel = None  # User left

    # Run listener
    await cog.on_voice_state_update(mock_member, before_state, after_state)
    assert mock_vc.disconnect.call_count == 1, "Bot failed to auto-disconnect when channel became empty!"
    print("[PASS] Bot auto-disconnected immediately when last member left voice channel.")

    print("\n[ALL VOICE RESTRICTION TESTS PASSED!]")

if __name__ == "__main__":
    asyncio.run(test_voice_restrictions())
