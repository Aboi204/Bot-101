import asyncio
import os
import re
import urllib.parse
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, List, Optional

import aiohttp
import yt_dlp

from src.utils.logger import log, record_error_trace, trace_and_log

BASE_DIR = Path(__file__).resolve().parent.parent.parent
COOKIES_FILE = BASE_DIR / "cookies" / "cookies.txt"
CACHE_AUDIO_DIR = BASE_DIR / "cache" / "audio"
CACHE_AUDIO_DIR.mkdir(parents=True, exist_ok=True)

@dataclass
class ResolvedTrack:
    title: str
    webpage_url: str
    stream_url: str
    duration: int
    thumbnail: Optional[str]
    uploader: str
    source_platform: str
    trace_id: str
    is_local_file: bool = False
    local_file_path: Optional[str] = None

    @property
    def formatted_duration(self) -> str:
        if self.duration <= 0:
            return "Live Stream / Unknown"
        mins, secs = divmod(self.duration, 60)
        hours, mins = divmod(mins, 60)
        return f"{hours}:{mins:02d}:{secs:02d}" if hours > 0 else f"{mins}:{secs:02d}"

class UnifiedAudioResolver:
    """
    Unified multi-source audio resolver optimized for instant direct streaming.
    1. YouTube (Instant single-video resolution, radio/mix cleanup, flat playlist fallback)
    2. SoundCloud
    3. Facebook
    4. Telegram
    5. Google Drive
    """

    YOUTUBE_VIDEO_RE = re.compile(r'(?:v=|/shorts/|youtu\.be/)([a-zA-Z0-9_-]{11})')
    YOUTUBE_PLAYLIST_RE = re.compile(r'[?&]list=([a-zA-Z0-9_-]+)')
    SOUNDCLOUD_RE = re.compile(r"https?://(?:www\.)?soundcloud\.com/[\w\-_]+/[\w\-_]+")
    FACEBOOK_RE = re.compile(r"https?://(?:www\.|m\.|web\.)?(?:facebook\.com|fb\.watch)/.+")
    TELEGRAM_RE = re.compile(r"https?://(?:www\.)?t\.me/([a-zA-Z0-9_]+)/([0-9]+)")
    GDRIVE_RE = re.compile(r"https?://drive\.google\.com/(?:file/d/([a-zA-Z0-9_-]+)|open\?id=([a-zA-Z0-9_-]+)|uc\?id=([a-zA-Z0-9_-]+))")

    def __init__(self):
        self.cookie_path = str(COOKIES_FILE) if COOKIES_FILE.exists() else None
        if self.cookie_path:
            log.info(f"Loaded cookie authentication from {self.cookie_path}")
        else:
            log.warning("No cookies.txt found in cookies/. Running unauthenticated.")

    def _build_ytdl_opts(self, platform_type: str = "generic", noplaylist: bool = True) -> Dict[str, Any]:
        opts: Dict[str, Any] = {
            'format': 'bestaudio/best',
            'noplaylist': noplaylist,
            'quiet': True,
            'no_warnings': True,
            'source_address': '0.0.0.0',
            'nocheckcertificate': True,
            'http_headers': {
                'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
                'Accept-Language': 'en-US,en;q=0.9',
            }
        }
        if self.cookie_path and os.path.exists(self.cookie_path) and os.path.getsize(self.cookie_path) > 100:
            opts['cookiefile'] = self.cookie_path

        if platform_type in ("facebook", "telegram", "gdrive"):
            opts['format'] = 'best[ext=mp4]/bestaudio/best'
        return opts

    @trace_and_log(platform_name="youtube", extract_url_arg="url_or_query")
    async def resolve_youtube(self, url_or_query: str, trace_id: str) -> List[ResolvedTrack]:
        loop = asyncio.get_running_loop()

        # Check if the URL contains a specific YouTube video ID
        v_match = self.YOUTUBE_VIDEO_RE.search(url_or_query)
        if v_match:
            video_id = v_match.group(1)
            # Strip radio mix, playlist params, timestamps to isolate the video and make extraction INSTANT
            clean_target = f"https://www.youtube.com/watch?v={video_id}"
            opts = self._build_ytdl_opts("youtube", noplaylist=True)

            def _extract_single():
                with yt_dlp.YoutubeDL(opts) as ydl:
                    return ydl.extract_info(clean_target, download=False)

            info = await loop.run_in_executor(None, _extract_single)
            if not info or not info.get('url'):
                raise ValueError(f"Could not extract direct stream URL for YouTube video: {clean_target}")

            return [ResolvedTrack(
                title=info.get('title', 'YouTube Audio'),
                webpage_url=clean_target,
                stream_url=info['url'],
                duration=int(info.get('duration', 0) or 0),
                thumbnail=info.get('thumbnail'),
                uploader=info.get('uploader', 'YouTube Uploader'),
                source_platform="youtube",
                trace_id=trace_id
            )]

        # If it's a pure playlist without a video ID
        elif "list=" in url_or_query and ("youtube.com" in url_or_query or "youtu.be" in url_or_query):
            # Extract flat to get tracklist instantly without resolving all streams upfront
            opts = self._build_ytdl_opts("youtube", noplaylist=False)
            opts['extract_flat'] = 'in_playlist'

            def _extract_playlist():
                with yt_dlp.YoutubeDL(opts) as ydl:
                    return ydl.extract_info(url_or_query, download=False)

            info = await loop.run_in_executor(None, _extract_playlist)
            entries = info.get('entries', [])
            if not entries:
                raise ValueError("No entries found in YouTube playlist.")

            # Resolve the first track immediately so streaming starts instantly
            first_entry = entries[0]
            first_url = first_entry.get('url') or f"https://www.youtube.com/watch?v={first_entry.get('id')}"
            first_track_list = await self.resolve_youtube(first_url, trace_id=trace_id)
            tracks = list(first_track_list)

            # Queue remaining tracks as placeholder entries that resolve on-demand
            for entry in entries[1:25]:  # Cap at 25 for fast response
                e_id = entry.get('id')
                if not e_id:
                    continue
                tracks.append(ResolvedTrack(
                    title=entry.get('title', 'Queued Video'),
                    webpage_url=f"https://www.youtube.com/watch?v={e_id}",
                    stream_url=f"https://www.youtube.com/watch?v={e_id}",  # will resolve just-in-time
                    duration=int(entry.get('duration', 0) or 0),
                    thumbnail=None,
                    uploader=entry.get('uploader', 'YouTube'),
                    source_platform="youtube",
                    trace_id=trace_id
                ))
            return tracks

        # Natural language search query
        else:
            target = f"ytsearch1:{url_or_query}"
            opts = self._build_ytdl_opts("youtube", noplaylist=True)

            def _extract_search():
                with yt_dlp.YoutubeDL(opts) as ydl:
                    return ydl.extract_info(target, download=False)

            info = await loop.run_in_executor(None, _extract_search)
            entries = info.get('entries') if info and 'entries' in info else [info]
            if not entries or not entries[0] or not entries[0].get('url'):
                raise ValueError(f"No search results found for query: {url_or_query}")

            entry = entries[0]
            return [ResolvedTrack(
                title=entry.get('title', 'YouTube Audio'),
                webpage_url=entry.get('webpage_url', entry.get('original_url', target)),
                stream_url=entry['url'],
                duration=int(entry.get('duration', 0) or 0),
                thumbnail=entry.get('thumbnail'),
                uploader=entry.get('uploader', 'YouTube Uploader'),
                source_platform="youtube",
                trace_id=trace_id
            )]

    @trace_and_log(platform_name="soundcloud", extract_url_arg="url_or_query")
    async def resolve_soundcloud(self, url_or_query: str, trace_id: str) -> List[ResolvedTrack]:
        loop = asyncio.get_running_loop()
        target = url_or_query if self.SOUNDCLOUD_RE.search(url_or_query) else f"scsearch1:{url_or_query}"
        opts = self._build_ytdl_opts("soundcloud", noplaylist=True)

        def _extract():
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(target, download=False)

        info = await loop.run_in_executor(None, _extract)
        tracks = []
        entries = info.get('entries') if info and 'entries' in info else [info]
        for entry in entries:
            if not entry or not entry.get('url'):
                continue
            tracks.append(ResolvedTrack(
                title=entry.get('title', 'SoundCloud Track'),
                webpage_url=entry.get('webpage_url', entry.get('original_url', target)),
                stream_url=entry.get('url'),
                duration=int(entry.get('duration', 0) or 0),
                thumbnail=entry.get('thumbnail'),
                uploader=entry.get('uploader', 'SoundCloud Artist'),
                source_platform="soundcloud",
                trace_id=trace_id
            ))
        return tracks

    @trace_and_log(platform_name="facebook", extract_url_arg="url")
    async def resolve_facebook(self, url: str, trace_id: str) -> List[ResolvedTrack]:
        loop = asyncio.get_running_loop()
        opts = self._build_ytdl_opts("facebook", noplaylist=True)

        def _extract():
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(url, download=False)

        info = await loop.run_in_executor(None, _extract)
        if not info or not info.get('url'):
            raise ValueError(f"Could not extract playable stream from Facebook URL: {url}")

        return [ResolvedTrack(
            title=info.get('title', 'Facebook Video Audio'),
            webpage_url=info.get('webpage_url', url),
            stream_url=info['url'],
            duration=int(info.get('duration', 0) or 0),
            thumbnail=info.get('thumbnail'),
            uploader=info.get('uploader', 'Facebook User'),
            source_platform="facebook",
            trace_id=trace_id
        )]

    @trace_and_log(platform_name="telegram", extract_url_arg="url")
    async def resolve_telegram(self, url: str, trace_id: str) -> List[ResolvedTrack]:
        loop = asyncio.get_running_loop()
        opts = self._build_ytdl_opts("telegram", noplaylist=True)

        def _extract():
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(url, download=False)

        try:
            info = await loop.run_in_executor(None, _extract)
            if info and info.get('url'):
                return [ResolvedTrack(
                    title=info.get('title', 'Telegram Audio Stream'),
                    webpage_url=info.get('webpage_url', url),
                    stream_url=info['url'],
                    duration=int(info.get('duration', 0) or 0),
                    thumbnail=info.get('thumbnail'),
                    uploader=info.get('uploader', 'Telegram Channel'),
                    source_platform="telegram",
                    trace_id=trace_id
                )]
        except Exception as e:
            log.warning(f"Telegram native extraction failed, attempting embed parsing: {e}")

        # Fallback to web embed
        match = self.TELEGRAM_RE.search(url)
        if not match:
            raise ValueError(f"Invalid Telegram URL: {url}")
        channel, msg_id = match.group(1), match.group(2)
        embed_url = f"https://t.me/{channel}/{msg_id}?embed=1"
        headers = {"User-Agent": "Mozilla/5.0"}
        async with aiohttp.ClientSession(headers=headers) as session:
            async with session.get(embed_url) as resp:
                if resp.status != 200:
                    raise ConnectionError(f"HTTP {resp.status} on Telegram embed")
                html = await resp.text()

        media_match = re.search(r'<(?:audio|video)[^>]+src=["\']([^"\']+)["\']', html)
        if media_match:
            src = media_match.group(1)
            if src.startswith("/"):
                src = f"https://t.me{src}"
            return [ResolvedTrack(
                title=f"Telegram Audio ({channel}/{msg_id})",
                webpage_url=url,
                stream_url=src,
                duration=0,
                thumbnail=None,
                uploader=f"@{channel}",
                source_platform="telegram",
                trace_id=trace_id
            )]

        raise ValueError(f"Could not locate playable audio in Telegram URL: {url}")

    @trace_and_log(platform_name="google_drive", extract_url_arg="url")
    async def resolve_gdrive(self, url: str, trace_id: str) -> List[ResolvedTrack]:
        loop = asyncio.get_running_loop()
        opts = self._build_ytdl_opts("gdrive", noplaylist=True)

        def _extract():
            with yt_dlp.YoutubeDL(opts) as ydl:
                return ydl.extract_info(url, download=False)

        info = await loop.run_in_executor(None, _extract)
        if not info or not info.get('url'):
            raise ValueError(f"Could not extract stream from Google Drive URL: {url}")

        return [ResolvedTrack(
            title=info.get('title', 'Google Drive Media'),
            webpage_url=info.get('webpage_url', url),
            stream_url=info['url'],
            duration=int(info.get('duration', 0) or 0),
            thumbnail=info.get('thumbnail'),
            uploader="Google Drive",
            source_platform="google_drive",
            trace_id=trace_id
        )]

    async def resolve(self, query_or_url: str, trace_id: Optional[str] = None) -> List[ResolvedTrack]:
        if not trace_id:
            from src.utils.logger import generate_trace_id
            trace_id = generate_trace_id()

        query_or_url = query_or_url.strip()

        if self.YOUTUBE_VIDEO_RE.search(query_or_url) or "youtube.com" in query_or_url or "youtu.be" in query_or_url:
            return await self.resolve_youtube(query_or_url, trace_id=trace_id)
        elif self.SOUNDCLOUD_RE.search(query_or_url):
            return await self.resolve_soundcloud(query_or_url, trace_id=trace_id)
        elif self.FACEBOOK_RE.search(query_or_url):
            return await self.resolve_facebook(query_or_url, trace_id=trace_id)
        elif self.TELEGRAM_RE.search(query_or_url):
            return await self.resolve_telegram(query_or_url, trace_id=trace_id)
        elif self.GDRIVE_RE.search(query_or_url):
            return await self.resolve_gdrive(query_or_url, trace_id=trace_id)
        else:
            return await self.resolve_youtube(query_or_url, trace_id=trace_id)
