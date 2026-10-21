import asyncio
import os
import random
import shutil
import sys
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
DEFAULT_VOLUME = float(os.getenv("DEFAULT_VOLUME", "1.0"))

def download_portable_ffmpeg(target_dir: Path) -> Optional[str]:
    """Downloads a portable ffmpeg.exe to target_dir/bin/ffmpeg.exe if not found on the system."""
    import urllib.request
    import zipfile

    bin_dir = target_dir / "bin"
    bin_dir.mkdir(parents=True, exist_ok=True)
    target_ffmpeg = bin_dir / "ffmpeg.exe"
    if target_ffmpeg.is_file():
        return str(target_ffmpeg)

    print("\n[*] FFmpeg is required for voice playback on Discord.")
    print("[*] Downloading portable FFmpeg (one-time automatic setup)...")
    url = "https://github.com/ffbinaries/ffbinaries-prebuilt/releases/download/v6.1/ffmpeg-6.1-win-64.zip"
    zip_dest = bin_dir / "ffmpeg_temp.zip"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=45) as resp, open(zip_dest, "wb") as out_f:
            total_size = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            while chunk := resp.read(64 * 1024):
                out_f.write(chunk)
                downloaded += len(chunk)
                if total_size > 0:
                    pct = int(downloaded / total_size * 100)
                    print(f"\r[*] Downloading FFmpeg: {pct}% ({round(downloaded / (1024*1024), 1)}MB / {round(total_size / (1024*1024), 1)}MB)...", end="", flush=True)
        print("\n[*] Extracting FFmpeg...")
        with zipfile.ZipFile(zip_dest, "r") as zf:
            for member in zf.namelist():
                if member.endswith("ffmpeg.exe"):
                    with zf.open(member) as source, open(target_ffmpeg, "wb") as target:
                        shutil.copyfileobj(source, target)
                    break
        if zip_dest.exists():
            zip_dest.unlink()
        print(f"[OK] FFmpeg ready at: {target_ffmpeg}\n")
        return str(target_ffmpeg)
    except Exception as e:
        print(f"\n[!] Automatic FFmpeg download failed: {e}")
        if zip_dest.exists():
            try:
                zip_dest.unlink()
            except Exception:
                pass
        return None

def get_ffmpeg_executable() -> str:
    # 1. Bundled PyInstaller temporary folder
    if getattr(sys, "frozen", False) and hasattr(sys, "_MEIPASS"):
        for bundled in [
            Path(sys._MEIPASS) / "ffmpeg.exe",
            Path(sys._MEIPASS) / "bin" / "ffmpeg.exe",
        ]:
            if bundled.is_file():
                return str(bundled)

    # 2. Local portable bundle directories next to executable or script
    app_dir = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent.parent.parent
    for candidate in [
        app_dir / "bin" / "ffmpeg.exe",
        app_dir / "ffmpeg.exe",
        Path.cwd() / "bin" / "ffmpeg.exe",
        Path.cwd() / "ffmpeg.exe",
    ]:
        if candidate.is_file():
            return str(candidate)

    # 3. System PATH
    which_ffmpeg = shutil.which("ffmpeg")
    if which_ffmpeg:
        return which_ffmpeg

    # 4. Windows Winget fallback path
    local_app = os.environ.get("LOCALAPPDATA", "")
    if local_app:
        winget_pattern = Path(local_app) / "Microsoft" / "WinGet" / "Packages"
        if winget_pattern.exists():
            for p in winget_pattern.glob("*FFmpeg*/**/ffmpeg.exe"):
                if p.is_file():
                    return str(p)

    # 5. Automatic download if missing on recipient's machine
    downloaded = download_portable_ffmpeg(app_dir)
    if downloaded:
        return downloaded

    return "ffmpeg"

class LoopMode(Enum):
    OFF = "off"
    TRACK = "track"
    QUEUE = "queue"

class PrebufferedAudioSource(discord.AudioSource):
    """
    Wraps an AudioSource and pre-buffers initial audio frames synchronously
    before discord.py's AudioPlayer thread starts its timing clock.
    This eliminates network-delay burst transmission (the 2x fast-forward speedup in the 1st second).
    """
    def __init__(self, original: discord.AudioSource, prebuffer_count: int = 8):
        self.original = original
        self.buffer = deque()
        for _ in range(prebuffer_count):
            try:
                data = self.original.read()
                if not data:
                    break
                self.buffer.append(data)
            except Exception:
                break

    def is_opus(self) -> bool:
        return self.original.is_opus()

    def read(self) -> bytes:
        if self.buffer:
            return self.buffer.popleft()
        return self.original.read()

    @property
    def volume(self) -> float:
        if hasattr(self.original, 'volume'):
            return self.original.volume
        return 1.0

    @volume.setter
    def volume(self, val: float) -> None:
        if hasattr(self.original, 'volume'):
            self.original.volume = val

    def cleanup(self) -> None:
        self.buffer.clear()
        self.original.cleanup()

class GuildVoiceManager:
    """
    Manages queue, playback, history navigation, voice watchdog self-healing with -ss dynamic resume,
    feature-complete interactive chat buttons, and direct low-latency audio streaming for a single Discord guild.
    """

    FFMPEG_OPTIONS = {
        'before_options': '-reconnect 1 -reconnect_at_eof 0 -reconnect_delay_max 5 -nostdin -user_agent "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"',
        'options': '-vn -filter:a loudnorm=I=-10:TP=-0.3:LRA=7'
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
        self.is_skipping: bool = False
        self.is_replaying: bool = False

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
        elif self.current is None:
            if self.voice_client and (self.voice_client.is_playing() or self.voice_client.is_paused()):
                self.voice_client.stop()
            self.play_next_event.set()

    def start_worker(self):
        if not self.worker_task or self.worker_task.done():
            self.worker_task = asyncio.create_task(self._playback_loop())

    async def _playback_loop(self):
        log.info(f"Playback dispatcher loop started for guild {self.guild.id}")
        while True:
            self.play_next_event.clear()

            # Record history when finished naturally
            if self.current and not self.is_recovering and not self.is_replaying:
                self.history.append(self.current)

            if self.is_skipping:
                self.is_skipping = False
                self.is_replaying = False
                next_track = self.queue.popleft() if self.queue else None
            elif self.is_replaying and self.current:
                self.is_replaying = False
                next_track = self.current
            elif self.current and self.loop_mode == LoopMode.TRACK and not self.is_recovering:
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
                if self.voice_client and (self.voice_client.is_playing() or self.voice_client.is_paused()):
                    self.voice_client.stop()

                await self.update_now_playing_message()

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
            volume_source = discord.PCMVolumeTransformer(raw_source, volume=self.volume)
            # Smooth pre-buffered audio source eliminates 2x initial burst speedup
            audio_source = PrebufferedAudioSource(volume_source, prebuffer_count=8)

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

                # Reset voice client playing state cleanly
                if self.voice_client and (self.voice_client.is_playing() or self.voice_client.is_paused()):
                    self.voice_client.stop()

                self.bot.loop.call_soon_threadsafe(self.play_next_event.set)

            # Ensure previous playback state is clean before starting
            if self.voice_client.is_playing() or self.voice_client.is_paused():
                self.voice_client.stop()

            self.voice_client.play(audio_source, after=_after_stream)

            # Update Now Playing embed with interactive control buttons in-place
            if seek_seconds == 0:
                await self.update_now_playing_message()

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

    async def update_now_playing_message(self, force_new: bool = False):
        """
        Updates the active Now Playing embed and interactive control buttons in-place.
        Prevents duplicate messages, orphan buttons, and interaction desynchronization.
        """
        if not self.text_channel:
            return

        embed = build_now_playing_embed(self)
        if not self.current_view:
            self.current_view = MusicControlView(self)
        else:
            self.current_view._update_button_states()

        # If playback is stopped (no track active), disable all buttons
        if not self.current:
            for child in self.current_view.children:
                child.disabled = True

        # If forced to create a new message (e.g. via /nowplaying), disable old buttons
        if force_new and self.current_message:
            try:
                for child in self.current_view.children:
                    child.disabled = True
                await self.current_message.edit(view=self.current_view)
            except Exception:
                pass
            self.current_message = None
            self.current_view = MusicControlView(self)

        # Try updating the existing message in-place
        if self.current_message:
            try:
                await self.current_message.edit(embed=embed, view=self.current_view)
                return
            except (discord.NotFound, discord.HTTPException):
                self.current_message = None

        # Only post a new message if there is an active track
        if self.current:
            try:
                self.current_message = await self.text_channel.send(embed=embed, view=self.current_view)
            except Exception as e:
                log.warning(f"Failed to send now playing message: {e}")

    def play_previous(self) -> bool:
        """Navigates back to the previously played track."""
        if not self.history:
            return False
        prev_track = self.history.pop()
        if self.current:
            self.queue.appendleft(self.current)
        self.queue.appendleft(prev_track)
        self.current = None
        self.is_recovering = False
        if self.voice_client and (self.voice_client.is_playing() or self.voice_client.is_paused()):
            self.voice_client.stop()
        else:
            self.play_next_event.set()
        return True

    def replay_current(self) -> bool:
        """Replays current track from the beginning (0s)."""
        if not self.current:
            return False
        self.is_replaying = True
        self.is_recovering = False
        self.track_start_time = time.time()
        self.total_paused_duration = 0.0
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
        self.is_replaying = False
        self.is_skipping = True
        if self.voice_client and (self.voice_client.is_playing() or self.voice_client.is_paused()):
            self.voice_client.stop()
        else:
            self.play_next_event.set()

    def stop(self):
        self.is_recovering = False
        self.is_replaying = False
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
            if hasattr(self.voice_client.source, 'volume'):
                self.voice_client.source.volume = self.volume

    def adjust_volume(self, delta_percent: int) -> int:
        current_pct = int(round(self.volume * 100))
        new_pct = max(10, min(current_pct + delta_percent, 200))
        self.set_volume(new_pct)
        return new_pct

    def shuffle_queue(self) -> int:
        if not self.queue:
            return 0
        q_list = list(self.queue)
        random.shuffle(q_list)
        self.queue = deque(q_list)
        return len(self.queue)

    def cycle_loop_mode(self) -> LoopMode:
        if self.loop_mode == LoopMode.OFF:
            self.loop_mode = LoopMode.TRACK
        elif self.loop_mode == LoopMode.TRACK:
            self.loop_mode = LoopMode.QUEUE
        else:
            self.loop_mode = LoopMode.OFF
        return self.loop_mode

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
                await self.update_now_playing_message()
        except asyncio.CancelledError:
            pass

    async def cleanup(self):
        self.stop()
        if self.worker_task:
            self.worker_task.cancel()
        self._cancel_idle_timer()
        if self.voice_client and self.voice_client.is_connected():
            await self.voice_client.disconnect()
