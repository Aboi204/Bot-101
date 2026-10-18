---
name: multi-source-audio-resolver
description: >-
  Resolves playable audio streams and manages temporary disk caching for YouTube, SoundCloud,
  Facebook, Telegram, and Google Drive URLs. Use when building or debugging audio extractors
  and FFmpeg streaming pipelines.
---

# Multi-Source Audio Resolver

High-fidelity audio streaming across diverse online media platforms requires unified extraction logic, custom session headers, and specialized fallback paths.

---

## 1. Routing Protocol

| Source Platform | Detection Pattern | Resolution Strategy |
| :--- | :--- | :--- |
| **YouTube** | `youtube.com`, `youtu.be` | `yt-dlp` using `cookies/cookies.txt`, `format: bestaudio/best`, User-Agent emulation, `noplaylist: False`. |
| **SoundCloud** | `soundcloud.com` | `yt-dlp` using native SoundCloud extractor, resolving HLS/progressive streams. |
| **Facebook** | `facebook.com`, `fb.watch` | `yt-dlp` with Facebook session cookies from Chrome, resolving SD/HD MP4 video/audio streams. |
| **Telegram** | `t.me/<channel>/<msg_id>` | `Telethon` client or direct web embed extractor (`https://t.me/<channel>/<msg_id>?embed=1`), caching audio locally to `cache/audio/<trace_id>.ogg` with guaranteed deletion post-playback. |
| **Google Drive** | `drive.google.com/file/d/<id>` | Direct stream/download resolver bypassing virus scan warning (`uc?export=download&confirm=t`) with session cookies. |

---

## 2. Audio Extraction Specification

### YouTube, SoundCloud & Facebook
```python
YTDL_OPTS = {
    'format': 'bestaudio/best',
    'noplaylist': False,
    'quiet': True,
    'no_warnings': True,
    'cookiefile': 'cookies/cookies.txt',
    'user_agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'source_address': '0.0.0.0',
}
```

### Telegram Audio Handling
- Public channel posts (`https://t.me/channel/123`):
  Fetch `https://t.me/channel/123?embed=1` to parse the underlying audio/video tag `src="..."` or stream directly.
- Download media into `cache/audio/<trace_id>.ogg` if direct streaming is restricted.
- Always guarantee file removal inside the `after` callback of `voice_client.play()`.

### Google Drive Direct Stream
- Extract file ID from URL: `re.search(r'/d/([a-zA-Z0-9_-]+)', url)`
- Build direct export URL: `https://drive.google.com/uc?export=download&id=<id>&confirm=t`
- Follow redirects and stream headers using `aiohttp` or `urllib`.

---

## 3. Streaming and Decoding Pipeline

Always supply resilient FFmpeg stream reconnection flags:
```python
FFMPEG_BEFORE_OPTIONS = "-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -nostdin"
FFMPEG_OPTIONS = "-vn"
```
For resuming playback after mid-song connection drops, inject dynamic `-ss <elapsed_seconds>` before the input stream.
