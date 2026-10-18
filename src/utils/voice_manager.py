import asyncio
import os
import shutil
import time
from collections import deque
from enum import Enum
from pathlib import Path
from typing import Deque, Optional

import discord

from src.extractors.unified_resolver import ResolvedTrack, UnifiedAudioResolver
from src.utils.logger import log, record_error_trace
from src.utils.ui_controls import MusicControlView, build_now_playing_embed

IDLE_TIMEOUT_SECONDS = 300  # 5 minutes
DEFAULT_VOLUME = float(os.getenv("DEFAULT_VOLUME", "1.0"))  # Default 100% loud and clear

def get_ffmpeg_executable() -> str:
    which_ffmpeg = shutil.which("ffmpeg")
    if which_ffmpeg:
        return which_ffmpeg

    # Windows winget fallback path
    win_path = Path(r"C:\Users\ISLAM\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.2-full_build\bin\ffmpeg.exe")
    if win_path.exists():
        return str(win_path)

    return "ffmpeg"

class LoopMode(Enum):
    OFF = "off"
    TRACK = "track"
    QUEUE = "queue"

class GuildVoiceManager:
    """
    Manages queue, playback, history navigation, voice watchdog self-healing with -ss dynamic resume,
    interactive chat buttons, and direct low-latency audio streaming for a single Discord guild.
    """

    FFMPEG_OPTIONS = {
        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -nostdin -user_agent "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"',
        'options': '-vn'
    }

    def __init__(self, bot: discord.Client, guild: discord.Guild, resolver: UnifiedAudioResolver):
        self.bot = bot
        self.guild = guild
        self.resolver = resolver
        self.queue: Deque[ResolvedTrack] = deque()
        self.history: Deque[ResolvedTrack] = deque(maxlen=50)
        self.current: Optional[ResolvedTrack] = None
        self.loop_mode: LoopMode = LoopMode.OFF
        self.volume: float = DEFAULT_VOLUME
        self.voice_client: Optional[discord.VoiceClient] = None
        self.text_channel: Optional[discord.TextChannel] = None
        self.ffmpeg_executable = get_ffmpeg_executable()

        self.current_message: Optional[discord.Message] = None
        self.current_view: Optional[MusicControlView] = None

        self.play_next_event = asyncio.Event()
        self.worker_task: Optional[asyncio.Task] = None
        self.idle_task: Optional[asyncio.Task] = None

        # Watchdog & self-healing state
        self.track_start_time: float = 0.0
        self.pause_start_time: float = 0.0
        self.total_paused_duration: float = 0.0
        self.retry_count: int = 0
        self.is_recovering: bool = False

    @property
    def is_playing(self) -> bool:
        return self.voice_client is not None and self.voice_client.is_playing()

    @property
    def is_paused(self) -> bool:
        return self.voice_client is not None and self.voice_client.is_paused()

    @property
    def elapsed_seconds(self) -> int:
        if not self.current or self.track_start_time == 0:
            return 0
        if self.is_paused:
            elapsed = self.pause_start_time - self.track_start_time - self.total_paused_duration
        else:
            elapsed = time.time() - self.track_start_time - self.total_paused_duration
        return max(0, int(elapsed))

    def enqueue(self, track: ResolvedTrack):
        """Adds a single track to the queue and triggers playback if idle."""
        self.queue.append(track)
        self.start_worker()
        self._check_and_trigger_playback()

    def enqueue_multiple(self, tracks: list[ResolvedTrack]):
        """Adds multiple tracks to the queue and triggers playback if idle."""
        for track in tracks:
            self.queue.append(track)
        self.start_worker()
        self._check_and_trigger_playback()

    def _check_and_trigger_playback(self):
        """Signals the playback dispatcher loop if no audio is actively streaming."""
        if not self.is_playing and not self.is_paused:
            self.play_next_event.set()

    def start_worker(self):
        if not self.worker_task or self.worker_task.done():
            self.worker_task = asyncio.create_task(self._playback_loop())

    async def _playback_loop(self):
        log.info(f"Playback dispatcher loop started for guild {self.guild.id}")
        while True:
            self.play_next_event.clear()

            # Record history when finished naturally
            if self.current and not self.is_recovering:
                self.history.append(self.current)

            if self.current and self.loop_mode == LoopMode.TRACK and not self.is_recovering:
                next_track = self.current
            elif self.current and self.loop_mode == LoopMode.QUEUE and not self.is_recovering:
                self.queue.append(self.current)
                next_track = self.queue.popleft() if self.queue else None
            elif self.is_recovering and self.current:
                next_track = self.current
            else:
                next_track = self.queue.popleft() if self.queue else None

            if not next_track:
                self.current = None
                log.info(f"Guild {self.guild.id} queue empty. Starting 5m idle watchdog.")
                self._start_idle_timer()
                await self.play_next_event.wait()
                self._cancel_idle_timer()
                continue

            self._cancel_idle_timer()

            # If placeholder URL from playlist, resolve actual stream URL just-in-time
            if next_track.stream_url.startswith("https://www.youtube.com/watch?v=") and "googlevideo.com" not in next_track.stream_url:
                try:
                    resolved_list = await self.resolver.resolve_youtube(next_track.stream_url, trace_id=next_track.trace_id)
                    if resolved_list:
                        next_track = resolved_list[0]
                except Exception as e:
                    log.error(f"Failed to resolve placeholder track: {e}")

            self.current = next_track
            await self._stream_track(next_track, seek_seconds=self.elapsed_seconds if self.is_recovering else 0)
            self.is_recovering = False
            await self.play_next_event.wait()

    async def _stream_track(self, track: ResolvedTrack, seek_seconds: int = 0):
        if not self.voice_client or not self.voice_client.is_connected():
            log.warning(f"Voice client not connected in guild {self.guild.id}")
            self.current = None
            self.play_next_event.set()
            return

        try:
            # Reconnect & dynamic seek option if recovering
            before_opts = self.FFMPEG_OPTIONS['before_options']
            if seek_seconds > 0:
                before_opts = f"-ss {seek_seconds} " + before_opts

            # Low latency direct stream pipe
            raw_source = discord.FFmpegPCMAudio(
                track.stream_url,
                executable=self.ffmpeg_executable,
                before_options=before_opts,
                options=self.FFMPEG_OPTIONS['options']
            )
            audio_source = discord.PCMVolumeTransformer(raw_source, volume=self.volume)

            if seek_seconds == 0:
                self.track_start_time = time.time()
                self.total_paused_duration = 0.0
                self.retry_count = 0

            def _after_stream(error):
                if error:
                    log.error(f"FFmpeg stream interrupted on {track.title}: {error}", extra={"trace_id": track.trace_id, "guild_id": self.guild.id})
                    if self.retry_count < 3 and self.elapsed_seconds < (track.duration or 3600) - 5:
                        self.retry_count += 1
                        self.is_recovering = True
                        log.info(f"Self-healer triggered: Resuming {track.title} at {self.elapsed_seconds}s (attempt {self.retry_count}/3)", extra={"trace_id": track.trace_id, "guild_id": self.guild.id})
                    else:
                        self.is_recovering = False
                        self._cleanup_track_cache(track)
                else:
                    log.info(f"Finished playing: {track.title}", extra={"trace_id": track.trace_id, "guild_id": self.guild.id})
                    self._cleanup_track_cache(track)

                self.bot.loop.call_soon_threadsafe(self.play_next_event.set)

            self.voice_client.play(audio_source, after=_after_stream)

            # Send Now Playing embed with interactive control buttons
            if seek_seconds == 0 and self.text_channel:
                embed = build_now_playing_embed(self)
                self.current_view = MusicControlView(self)
                self.current_message = await self.text_channel.send(embed=embed, view=self.current_view)

        except Exception as e:
            log.error(f"Failed to initialize FFmpeg stream for {track.title}: {e}", exc_info=True, extra={"trace_id": track.trace_id, "guild_id": self.guild.id})
            record_error_trace(
                trace_id=track.trace_id,
                exception=e,
                guild_id=self.guild.id,
                source_platform=track.source_platform,
                input_url=track.webpage_url
            )
            self._cleanup_track_cache(track)
            self.play_next_event.set()

    def play_previous(self) -> bool:
        """Plays the previously played track from history."""
        if not self.history:
            return False

        prev_track = self.history.pop()
        if self.current:
            self.queue.appendleft(self.current)

        self.current = prev_track
        self.is_recovering = True  # flags dispatcher to play this track directly
        if self.voice_client and (self.voice_client.is_playing() or self.voice_client.is_paused()):
            self.voice_client.stop()
        else:
            self.play_next_event.set()
        return True

    def replay_current(self) -> bool:
        """Restarts the currently playing track from the beginning."""
        if not self.current:
            return False
        self.track_start_time = time.time()
        self.total_paused_duration = 0.0
        self.is_recovering = True
        if self.voice_client and (self.voice_client.is_playing() or self.voice_client.is_paused()):
            self.voice_client.stop()
        else:
            self.play_next_event.set()
        return True

    def _cleanup_track_cache(self, track: ResolvedTrack):
        """Removes temporary cached audio files post-playback."""
        if track.is_local_file and track.local_file_path and os.path.exists(track.local_file_path):
            try:
                os.remove(track.local_file_path)
                log.info(f"Cleaned up temporary cache: {track.local_file_path}", extra={"trace_id": track.trace_id})
            except Exception as e:
                log.warning(f"Error removing temp cache {track.local_file_path}: {e}")

    def pause(self):
        if self.voice_client and self.voice_client.is_playing():
            self.voice_client.pause()
            self.pause_start_time = time.time()

    def resume(self):
        if self.voice_client and self.voice_client.is_paused():
            self.voice_client.resume()
            if self.pause_start_time > 0:
                self.total_paused_duration += time.time() - self.pause_start_time
                self.pause_start_time = 0.0

    def skip(self):
        self.is_recovering = False
        if self.voice_client and (self.voice_client.is_playing() or self.voice_client.is_paused()):
            self.voice_client.stop()

    def stop(self):
        self.is_recovering = False
        if self.current:
            self.history.append(self.current)
        self.queue.clear()
        self.current = None
        self.loop_mode = LoopMode.OFF
        if self.voice_client and (self.voice_client.is_playing() or self.voice_client.is_paused()):
            self.voice_client.stop()
        else:
            self.play_next_event.set()

    def set_volume(self, vol_percent: int):
        self.volume = max(0.01, min(vol_percent / 100.0, 2.0))
        if self.voice_client and self.voice_client.source:
            if isinstance(self.voice_client.source, discord.PCMVolumeTransformer):
                self.voice_client.source.volume = self.volume

    def _start_idle_timer(self):
        self._cancel_idle_timer()
        self.idle_task = asyncio.create_task(self._idle_worker())

    def _cancel_idle_timer(self):
        if self.idle_task and not self.idle_task.done():
            self.idle_task.cancel()
            self.idle_task = None

    async def _idle_worker(self):
        try:
            await asyncio.sleep(IDLE_TIMEOUT_SECONDS)
            if self.voice_client and self.voice_client.is_connected() and not self.current:
                log.info(f"Idle timeout reached for guild {self.guild.id}. Disconnecting voice client.")
                if self.text_channel:
                    await self.text_channel.send("👋 Disconnected due to 5 minutes of inactivity to conserve free RAM.")
                await self.voice_client.disconnect()
        except asyncio.CancelledError:
            pass

    async def cleanup(self):
        self.stop()
        if self.worker_task:
            self.worker_task.cancel()
        self._cancel_idle_timer()
        if self.voice_client and self.voice_client.is_connected():
            await self.voice_client.disconnect()
