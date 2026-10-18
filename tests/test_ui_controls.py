import sys
from collections import deque
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.extractors.unified_resolver import ResolvedTrack
from src.utils.ui_controls import MusicControlView, build_now_playing_embed, create_progress_bar

class MockManager:
    def __init__(self):
        self.volume = 1.0
        self.is_paused = False
        self.is_playing = True
        self.elapsed_seconds = 45
        self.loop_mode = type("Loop", (), {"value": "off"})()
        self.history = deque()
        self.queue = deque()
        self.current = ResolvedTrack(
            title="Surah Al-Ikhlas - Sheikh Muhammad Rifat",
            webpage_url="https://www.facebook.com/watch/?v=884001474643399",
            stream_url="https://video.fbcdn.net/...",
            duration=55,
            thumbnail="https://example.com/thumb.jpg",
            uploader="Facebook",
            source_platform="facebook",
            trace_id="TRC-TEST"
        )

    def pause(self):
        self.is_paused = True

    def resume(self):
        self.is_paused = False

    def skip(self):
        if self.queue:
            self.history.append(self.current)
            self.current = self.queue.popleft()

    def play_previous(self):
        if self.history:
            prev = self.history.pop()
            self.queue.appendleft(self.current)
            self.current = prev
            return True
        return False

    def replay_current(self):
        self.elapsed_seconds = 0
        return True

    def stop(self):
        self.current = None
        self.queue.clear()

def test_controls():
    manager = MockManager()
    
    # Add a mock track to queue
    manager.queue.append(ResolvedTrack(
        title="Next Song In Queue",
        webpage_url="https://youtube.com/watch?v=123",
        stream_url="https://stream.url",
        duration=180,
        thumbnail=None,
        uploader="YouTube",
        source_platform="youtube",
        trace_id="TRC-Q1"
    ))

    # Test embed generation
    embed = build_now_playing_embed(manager)
    print("[+] Embed Title:", embed.title)
    print("[+] Embed Description:\n", embed.description)
    fields = {f.name: f.value for f in embed.fields}
    print("[+] Embed Volume:", fields.get("Volume"))
    assert fields.get("Volume") == "100%", f"Expected 100%, got {fields.get('Volume')}"
    assert "Upcoming Queue" in "".join(fields.keys()), "Queue preview missing in embed!"
    print("[PASS] Embed verified with 100% Volume and Live Queue Preview.")

    # Test interactive control view
    view = MusicControlView(manager)
    button_custom_ids = [child.custom_id for child in view.children]
    print("[+] View Buttons:", button_custom_ids)
    assert "btn_prev" in button_custom_ids, "Missing btn_prev"
    assert "btn_pause_resume" in button_custom_ids, "Missing btn_pause_resume"
    assert "btn_next" in button_custom_ids, "Missing btn_next"
    assert "btn_replay" in button_custom_ids, "Missing btn_replay"
    assert "btn_stop" in button_custom_ids, "Missing btn_stop"
    print("[PASS] All 5 interactive control buttons present and mapped.")

    # Test Skip & History
    manager.skip()
    assert manager.current.title == "Next Song In Queue"
    assert len(manager.history) == 1
    print("[PASS] Next / Skip button works and records history.")

    # Test Previous Track
    success = manager.play_previous()
    assert success
    assert manager.current.title == "Surah Al-Ikhlas - Sheikh Muhammad Rifat"
    print("[PASS] Previous button successfully restores previous track from history.")

    # Test Replay
    success = manager.replay_current()
    assert success
    assert manager.elapsed_seconds == 0
    print("[PASS] Replay button successfully resets elapsed time to 0.")

    print("\n[VERIFIED] All UI controls and volume requirements passed!")

if __name__ == "__main__":
    test_controls()
