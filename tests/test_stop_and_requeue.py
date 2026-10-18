import asyncio
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.extractors.unified_resolver import ResolvedTrack, UnifiedAudioResolver
from src.utils.voice_manager import GuildVoiceManager

class MockVoiceClient:
    def __init__(self):
        self._playing = False
        self._paused = False
        self._connected = True
        self.source = None
        self.after_callback = None

    def is_connected(self):
        return self._connected

    async def disconnect(self, force=False):
        self._connected = False

    def is_playing(self):
        return self._playing

    def is_paused(self):
        return self._paused

    def play(self, source, after=None):
        self._playing = True
        self._paused = False
        self.source = source
        self.after_callback = after

    def pause(self):
        self._paused = True
        self._playing = False

    def resume(self):
        self._paused = False
        self._playing = True

    def stop(self):
        self._playing = False
        self._paused = False
        if self.after_callback:
            cb = self.after_callback
            self.after_callback = None
            cb(None)

async def run_lifecycle_test():
    bot = type("MockBot", (), {"loop": asyncio.get_running_loop()})()
    guild = type("MockGuild", (), {"id": 123456789})()
    resolver = UnifiedAudioResolver()

    manager = GuildVoiceManager(bot, guild, resolver)
    mock_vc = MockVoiceClient()
    manager.voice_client = mock_vc

    # Override _stream_track to mock audio playback without launching actual ffmpeg
    async def mock_stream_track(track: ResolvedTrack, seek_seconds: int = 0):
        if not manager.voice_client or not manager.voice_client.is_connected():
            manager.current = None
            manager.play_next_event.set()
            return

        def _after_stream(error):
            mock_vc._playing = False
            manager.bot.loop.call_soon_threadsafe(manager.play_next_event.set)

        mock_vc.play(None, after=_after_stream)

    manager._stream_track = mock_stream_track

    track1 = ResolvedTrack(
        title="Track 1 - Initial Song",
        webpage_url="https://youtube.com/watch?v=track1",
        stream_url="https://audio.stream/1",
        duration=100,
        thumbnail=None,
        uploader="Artist 1",
        source_platform="youtube",
        trace_id="TRC-T1"
    )

    track2 = ResolvedTrack(
        title="Track 2 - Second Song After Stop",
        webpage_url="https://youtube.com/watch?v=track2",
        stream_url="https://audio.stream/2",
        duration=120,
        thumbnail=None,
        uploader="Artist 2",
        source_platform="youtube",
        trace_id="TRC-T2"
    )

    print("[1] Enqueueing Track 1...")
    manager.enqueue(track1)
    await asyncio.sleep(0.05)

    assert manager.current is not None, "Track 1 should be current track"
    assert manager.current.title == "Track 1 - Initial Song"
    assert mock_vc.is_playing(), "Voice client should be playing Track 1"
    print("    [PASS] Track 1 started playing successfully.")

    print("\n[2] User triggers STOP command...")
    manager.stop()
    await asyncio.sleep(0.05)

    assert manager.current is None, "Current should be None after stop"
    assert len(manager.queue) == 0, "Queue should be empty after stop"
    assert not mock_vc.is_playing(), "Voice client should not be playing"
    print("    [PASS] Stop executed cleanly: queue empty, playback stopped.")

    print("\n[3] User adds Track 2 to queue (while bot is idle)...")
    manager.enqueue(track2)
    await asyncio.sleep(0.05)

    assert manager.current is not None, "Track 2 should immediately become current track!"
    assert manager.current.title == "Track 2 - Second Song After Stop"
    assert mock_vc.is_playing(), "Voice client should be playing Track 2!"
    print("    [PASS] Track 2 started streaming immediately without deadlock!")

    print("\n[4] Cleaning up...")
    await manager.cleanup()
    print("[ALL PASS] Stop and Requeue lifecycle verified successfully!")

if __name__ == "__main__":
    asyncio.run(run_lifecycle_test())
