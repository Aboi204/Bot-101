import asyncio
import time
from collections import deque
from enum import Enum
from typing import Deque, Optional

import discord
import config
from audio.resolver import AudioTrack
from utils.logger import log

class LoopMode(Enum):
    OFF = "off"
    TRACK = "track"
    QUEUE = "queue"

class GuildPlayer:
    """Manages audio queue, voice client state, playback lifecycle, and idle timeouts for a single guild."""

    FFMPEG_OPTIONS = {
        'before_options': '-reconnect 1 -reconnect_streamed 1 -reconnect_delay_max 5 -nostdin',
        'options': '-vn'
    }

    def __init__(self, bot: discord.Client, guild: discord.Guild):
        self.bot = bot
        self.guild = guild
        self.queue: Deque[AudioTrack] = deque()
        self.current: Optional[AudioTrack] = None
        self.loop_mode: LoopMode = LoopMode.OFF
        self.volume: float = config.DEFAULT_VOLUME
        self.voice_client: Optional[discord.VoiceClient] = None
        self.text_channel: Optional[discord.TextChannel] = None

        self.play_next_event = asyncio.Event()
        self.audio_task: Optional[asyncio.Task] = None
        self.idle_task: Optional[asyncio.Task] = None

        self.track_start_time: float = 0.0
        self.pause_start_time: float = 0.0
        self.total_paused_duration: float = 0.0

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
            current_elapsed = self.pause_start_time - self.track_start_time - self.total_paused_duration
        else:
            current_elapsed = time.time() - self.track_start_time - self.total_paused_duration
        return max(0, int(current_elapsed))

    def start_worker(self):
        """Starts the background audio dispatcher loop if not already running."""
        if not self.audio_task or self.audio_task.done():
            self.audio_task = asyncio.create_task(self._audio_dispatcher())

    async def _audio_dispatcher(self):
        """Worker loop that plays tracks sequentially from the queue."""
        log.info(f"Audio dispatcher started for guild {self.guild.name} ({self.guild.id})", extra={"event": "dispatcher_start", "guild_id": self.guild.id})

        while True:
            self.play_next_event.clear()

            # Handle looping mechanisms
            if self.current and self.loop_mode == LoopMode.TRACK:
                next_track = self.current
            elif self.current and self.loop_mode == LoopMode.QUEUE:
                self.queue.append(self.current)
                next_track = self.queue.popleft() if self.queue else None
            else:
                next_track = self.queue.popleft() if self.queue else None

            if not next_track:
                self.current = None
                log.info(f"Queue empty for guild {self.guild.id}. Starting idle timer.", extra={"event": "queue_empty", "guild_id": self.guild.id})
                self._start_idle_timer()
                await self.play_next_event.wait()
                self._cancel_idle_timer()
                continue

            self._cancel_idle_timer()
            self.current = next_track
            await self._play_track(next_track)
            await self.play_next_event.wait()

    async def _play_track(self, track: AudioTrack):
        """Prepares FFmpeg audio source and begins streaming to voice client."""
        if not self.voice_client or not self.voice_client.is_connected():
            log.warning(f"Voice client not connected for guild {self.guild.id}", extra={"event": "voice_not_connected", "guild_id": self.guild.id})
            return

        try:
            raw_source = discord.FFmpegPCMAudio(track.stream_url, **self.FFMPEG_OPTIONS)
            audio_source = discord.PCMVolumeTransformer(raw_source, volume=self.volume)

            self.track_start_time = time.time()
            self.total_paused_duration = 0.0

            def after_playback(error):
                if error:
                    log.error(f"FFmpeg error during playback: {error}", extra={"event": "ffmpeg_error", "guild_id": self.guild.id})
                else:
                    log.info(f"Playback ended for: {track.title}", extra={"event": "playback_end", "guild_id": self.guild.id})
                self.bot.loop.call_soon_threadsafe(self.play_next_event.set)

            self.voice_client.play(audio_source, after=after_playback)

            log.info(
                f"Started playing: {track.title} in {self.guild.name}",
                extra={"event": "playback_start", "guild_id": self.guild.id, "metadata": {"title": track.title, "url": track.webpage_url}}
            )

            # Send Now Playing embed to text channel
            if self.text_channel:
                embed = discord.Embed(
                    title="🎶 Now Playing",
                    description=f"[{track.title}]({track.webpage_url})",
                    color=discord.Color.blurple()
                )
                embed.add_field(name="Duration", value=track.formatted_duration, inline=True)
                embed.add_field(name="Uploader", value=track.uploader, inline=True)
                if track.requested_by:
                    embed.add_field(name="Requested By", value=track.requested_by, inline=True)
                if track.thumbnail:
                    embed.set_thumbnail(url=track.thumbnail)
                await self.text_channel.send(embed=embed)

        except Exception as e:
            log.error(f"Failed to play track {track.title}: {e}", exc_info=True, extra={"event": "playback_error", "guild_id": self.guild.id})
            self.play_next_event.set()

    def set_volume(self, volume: float):
        """Sets volume percentage (0.0 - 1.0)."""
        self.volume = max(0.0, min(volume, 2.0))
        if self.voice_client and self.voice_client.source:
            if isinstance(self.voice_client.source, discord.PCMVolumeTransformer):
                self.voice_client.source.volume = self.volume

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
        if self.voice_client and (self.voice_client.is_playing() or self.voice_client.is_paused()):
            # If skipping on single loop, move to next song
            if self.loop_mode == LoopMode.TRACK:
                self.loop_mode = LoopMode.OFF
            self.voice_client.stop()

    def stop(self):
        self.queue.clear()
        self.current = None
        self.loop_mode = LoopMode.OFF
        if self.voice_client and (self.voice_client.is_playing() or self.voice_client.is_paused()):
            self.voice_client.stop()

    def _start_idle_timer(self):
        self._cancel_idle_timer()
        self.idle_task = asyncio.create_task(self._idle_timeout_worker())

    def _cancel_idle_timer(self):
        if self.idle_task and not self.idle_task.done():
            self.idle_task.cancel()
            self.idle_task = None

    async def _idle_timeout_worker(self):
        try:
            await asyncio.sleep(config.IDLE_TIMEOUT_SECONDS)
            if self.voice_client and self.voice_client.is_connected() and not self.current:
                log.info(f"Idle timeout reached ({config.IDLE_TIMEOUT_SECONDS}s). Disconnecting from voice.", extra={"event": "idle_disconnect", "guild_id": self.guild.id})
                if self.text_channel:
                    await self.text_channel.send("👋 Disconnected due to inactivity to conserve server resources.")
                await self.voice_client.disconnect()
        except asyncio.CancelledError:
            pass

    async def cleanup(self):
        """Clean shutdown of guild player resources."""
        self.stop()
        if self.audio_task:
            self.audio_task.cancel()
        self._cancel_idle_timer()
        if self.voice_client and self.voice_client.is_connected():
            await self.voice_client.disconnect()
