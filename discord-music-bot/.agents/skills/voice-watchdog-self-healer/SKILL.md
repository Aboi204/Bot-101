---
name: voice-watchdog-self-healer
description: >-
  Monitors Discord voice WebSocket stability, detects mid-stream FFmpeg drops or HTTP 403 URL expirations,
  refreshes cookies automatically, and resumes playback from the exact elapsed timestamp (-ss).
  Use in the voice player and queue manager.
---

# Voice Watchdog Self-Healer

Streaming media sessions often encounter network jitter, YouTube stream URL signature expiration, or voice WebSocket packet drops. Rather than abruptly failing or skipping to the next track, the voice watchdog detects failures in real time and heals the stream seamlessly.

---

## 1. Failure Modes & Healing Actions

| Detected Failure | Detection Method | Autonomous Healing Action |
| :--- | :--- | :--- |
| **Mid-Stream FFmpeg Drop** | FFmpeg process exits unexpectedly before track duration is reached. | Calculate elapsed playback seconds and restart FFmpeg with `-ss <elapsed_seconds>`. |
| **HTTP 403 / 410 URL Expiry** | FFmpeg stderr outputs `Server returned 403 Forbidden`. | Invalidate cached stream URL, re-resolve direct URL using `unified_resolver`, and resume with `-ss`. |
| **Cookie Invalidation** | yt-dlp returns `Sign in to confirm you're not a bot`. | Trigger `export_cookies.py` to refresh `cookies/cookies.txt`, reload extractor, and retry. |
| **Voice Gateway Disconnect** | `VoiceClient.is_connected()` becomes `False` or receives voice error opcode. | Attempt automatic voice reconnection to the last channel within 10 seconds. |

---

## 2. Dynamic Stream Resume Implementation

When an active stream is interrupted:

```python
elapsed_sec = int(time.time() - track_start_time - paused_duration)

# Dynamic resume options with seek
ffmpeg_before = (
    f"-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 "
    f"-ss {elapsed_sec} -nostdin"
)

audio_source = discord.FFmpegPCMAudio(
    fresh_stream_url,
    before_options=ffmpeg_before,
    options="-vn"
)
voice_client.play(audio_source, after=after_playback_callback)
```

---

## 3. Playback State Tracking

The player maintains:
- `track_start_time`: Epoch seconds when playback started.
- `total_paused_time`: Cumulative duration spent in paused state.
- `retry_count`: Capped at 3 retries per track to avoid infinite error loops on corrupt files.
- `is_healing`: Boolean flag suppressing duplicate "Now Playing" messages during stream recovery.
