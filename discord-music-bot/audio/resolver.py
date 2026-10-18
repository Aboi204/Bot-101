import asyncio
import os
import re
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional
import urllib.request
import json

import yt_dlp
import config
from utils.logger import log

@dataclass
class AudioTrack:
    title: str
    webpage_url: str
    stream_url: str
    duration: int
    thumbnail: Optional[str]
    uploader: str
    extractor: str
    requested_by: Optional[str] = None

    @property
    def formatted_duration(self) -> str:
        if self.duration <= 0:
            return "Live Stream / Unknown"
        mins, secs = divmod(self.duration, 60)
        hours, mins = divmod(mins, 60)
        if hours > 0:
            return f"{hours}:{mins:02d}:{secs:02d}"
        return f"{mins}:{secs:02d}"

class AudioResolver:
    """Multi-source audio stream resolver using yt-dlp with cookie management and Spotify metadata mapping."""

    SPOTIFY_TRACK_RE = re.compile(r"https?://open\.spotify\.com/(?:intl-[a-z]+/)?track/([a-zA-Z0-9]+)")
    SPOTIFY_PLAYLIST_RE = re.compile(r"https?://open\.spotify\.com/(?:intl-[a-z]+/)?playlist/([a-zA-Z0-9]+)")
    SPOTIFY_ALBUM_RE = re.compile(r"https?://open\.spotify\.com/(?:intl-[a-z]+/)?album/([a-zA-Z0-9]+)")

    def __init__(self):
        self.cookie_file = config.COOKIE_FILE if os.path.exists(config.COOKIE_FILE) else None
        if self.cookie_file:
            log.info(f"Loaded cookie file for audio resolver: {self.cookie_file}", extra={"event": "auth_cookie_loaded"})
        else:
            log.warning("No cookie file found. Running unauthenticated (may encounter rate limits/403s on YouTube).", extra={"event": "auth_cookie_missing"})

        self.ydl_opts = {
            'format': 'bestaudio/best',
            'noplaylist': True,
            'quiet': True,
            'no_warnings': True,
            'default_search': 'ytsearch',
            'extract_flat': False,
            'source_address': '0.0.0.0',
            'nocheckcertificate': True,
        }
        if self.cookie_file:
            self.ydl_opts['cookiefile'] = self.cookie_file

    def _get_ydl(self, flat: bool = False) -> yt_dlp.YoutubeDL:
        opts = dict(self.ydl_opts)
        opts['extract_flat'] = flat
        return yt_dlp.YoutubeDL(opts)

    def _resolve_spotify_oembed(self, url: str) -> Optional[str]:
        """Resolve Spotify track title & artist via public oEmbed API without client secrets."""
        try:
            oembed_url = f"https://open.spotify.com/oembed?url={urllib.parse.quote(url)}"
            req = urllib.request.Request(oembed_url, headers={"User-Agent": "Mozilla/5.0"})
            with urllib.request.urlopen(req, timeout=5) as response:
                if response.status == 200:
                    data = json.loads(response.read().decode("utf-8"))
                    title = data.get("title")
                    if title:
                        return f"{title} audio"
        except Exception as e:
            log.warning(f"Spotify oEmbed fallback failed for {url}: {e}")
        return None

    def _extract_sync(self, query: str, user: Optional[str] = None) -> List[AudioTrack]:
        t0 = time.time()
        tracks: List[AudioTrack] = []

        # Check for Spotify URLs
        if self.SPOTIFY_TRACK_RE.search(query):
            mapped_query = self._resolve_spotify_oembed(query)
            if mapped_query:
                log.info(f"Resolved Spotify link '{query}' to '{mapped_query}'", extra={"event": "spotify_mapped"})
                query = f"ytsearch:{mapped_query}"

        # Determine target
        if not (query.startswith("http://") or query.startswith("https://") or query.startswith("ytsearch:") or query.startswith("scsearch:")):
            target = f"ytsearch:{query}"
        else:
            target = query

        ydl = self._get_ydl(flat=False)
        try:
            info = ydl.extract_info(target, download=False)
            if not info:
                return tracks

            entries = info['entries'] if 'entries' in info else [info]

            for entry in entries:
                if not entry:
                    continue
                stream_url = entry.get('url')
                if not stream_url:
                    continue

                track = AudioTrack(
                    title=entry.get('title', 'Unknown Title'),
                    webpage_url=entry.get('webpage_url', entry.get('original_url', target)),
                    stream_url=stream_url,
                    duration=int(entry.get('duration', 0) or 0),
                    thumbnail=entry.get('thumbnail'),
                    uploader=entry.get('uploader', 'Unknown Artist'),
                    extractor=entry.get('extractor_key', entry.get('extractor', 'Generic')),
                    requested_by=user
                )
                tracks.append(track)

            duration_ms = (time.time() - t0) * 1000
            log.info(
                f"Resolved {len(tracks)} track(s) for query: {query}",
                extra={"event": "resolve_success", "metadata": {"duration_ms": duration_ms, "tracks_count": len(tracks)}}
            )

        except Exception as e:
            log.error(f"Error resolving query '{query}': {e}", exc_info=True, extra={"event": "resolve_error"})
            raise e

        return tracks

    async def resolve(self, query: str, user: Optional[str] = None) -> List[AudioTrack]:
        """Asynchronously resolve query using worker thread to avoid blocking event loop."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self._extract_sync, query, user)
