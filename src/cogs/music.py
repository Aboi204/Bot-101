import datetime
import json
import os
import platform
import time
from typing import Dict, Literal, Optional

import discord
from discord import app_commands
from discord.ext import commands
import psutil

from src.extractors.unified_resolver import UnifiedAudioResolver
from src.utils.logger import (
    ERROR_TRACES_FILE,
    generate_trace_id,
    log,
    record_error_trace,
    trace_and_log,
)
from src.utils.voice_manager import GuildVoiceManager, LoopMode
from src.utils.ui_controls import MusicControlView, build_now_playing_embed, create_progress_bar

class MusicCog(commands.Cog, name="Music"):
    """Multi-source music streaming commands and diagnostic telemetry."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.resolver = UnifiedAudioResolver()
        self.managers: Dict[int, GuildVoiceManager] = {}
        self.bot_start_time = time.time()

    def get_manager(self, guild: discord.Guild) -> GuildVoiceManager:
        if guild.id not in self.managers:
            self.managers[guild.id] = GuildVoiceManager(self.bot, guild, self.resolver)
        return self.managers[guild.id]

    async def _ensure_voice(self, interaction: discord.Interaction) -> Optional[discord.VoiceClient]:
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message("❌ You must be connected to a voice channel.", ephemeral=True)
            return None

        channel = interaction.user.voice.channel
        vc = interaction.guild.voice_client

        if vc is None:
            vc = await channel.connect()
        elif vc.channel != channel:
            await vc.move_to(channel)

        return vc

    @app_commands.command(name="play", description="Stream audio from YouTube, SoundCloud, Facebook, Telegram, or Google Drive")
    @app_commands.describe(query="Song title, search keywords, or URL (YouTube, SoundCloud, Facebook, Telegram, Drive)")
    async def play(self, interaction: discord.Interaction, query: str):
        trace_id = generate_trace_id()
        await interaction.response.defer()

        vc = await self._ensure_voice(interaction)
        if not vc:
            return

        manager = self.get_manager(interaction.guild)
        manager.voice_client = vc
        manager.text_channel = interaction.channel

        try:
            tracks = await self.resolver.resolve(query, trace_id=trace_id)
        except Exception as e:
            await interaction.followup.send(f"❌ Failed to extract audio: `{e}`\nTrace-ID: `{trace_id}`")
            return

        if not tracks:
            await interaction.followup.send(f"❌ No playable audio streams found.\nTrace-ID: `{trace_id}`")
            return

        for track in tracks:
            manager.queue.append(track)

        manager.start_worker()

        if len(tracks) == 1:
            track = tracks[0]
            embed = discord.Embed(
                title="Added to Queue",
                description=f"[{track.title}]({track.webpage_url})",
                color=discord.Color.green()
            )
            embed.add_field(name="Source", value=track.source_platform.replace("_", " ").title(), inline=True)
            embed.add_field(name="Duration", value=track.formatted_duration, inline=True)
            embed.add_field(name="Position in Queue", value=str(len(manager.queue)), inline=True)
            embed.set_footer(text=f"Trace-ID: {trace_id} • Fast Direct Streaming")
            if track.thumbnail:
                embed.set_thumbnail(url=track.thumbnail)
            await interaction.followup.send(embed=embed)
        else:
            embed = discord.Embed(
                title="Playlist / Multi-Track Queued",
                description=f"Enqueued **{len(tracks)}** tracks from {tracks[0].source_platform.title()}.",
                color=discord.Color.green()
            )
            embed.set_footer(text=f"Trace-ID: {trace_id}")
            await interaction.followup.send(embed=embed)

    @app_commands.command(name="pause", description="Pause active audio playback")
    async def pause(self, interaction: discord.Interaction):
        manager = self.get_manager(interaction.guild)
        if not manager.is_playing:
            await interaction.response.send_message("❌ Nothing is currently playing.", ephemeral=True)
            return
        manager.pause()
        await interaction.response.send_message("⏸️ Playback paused.")

    @app_commands.command(name="resume", description="Resume paused audio playback")
    async def resume(self, interaction: discord.Interaction):
        manager = self.get_manager(interaction.guild)
        if not manager.is_paused:
            await interaction.response.send_message("❌ Playback is not paused.", ephemeral=True)
            return
        manager.resume()
        await interaction.response.send_message("▶️ Playback resumed.")

    @app_commands.command(name="skip", description="Skip to the next song in the queue")
    async def skip(self, interaction: discord.Interaction):
        manager = self.get_manager(interaction.guild)
        if not manager.current:
            await interaction.response.send_message("❌ Nothing is currently playing.", ephemeral=True)
            return
        title = manager.current.title
        manager.skip()
        await interaction.response.send_message(f"⏭️ Skipped: **{title}**")

    @app_commands.command(name="stop", description="Stop playback and clear the queue")
    async def stop(self, interaction: discord.Interaction):
        manager = self.get_manager(interaction.guild)
        manager.stop()
        await interaction.response.send_message("⏹️ Playback stopped and queue cleared.")

    @app_commands.command(name="nowplaying", description="Show detailed info and dynamic controls of current song")
    async def nowplaying(self, interaction: discord.Interaction):
        manager = self.get_manager(interaction.guild)
        if not manager.current:
            await interaction.response.send_message("❌ Nothing is currently playing.", ephemeral=True)
            return

        embed = build_now_playing_embed(manager)
        view = MusicControlView(manager)
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="queue", description="Display the list of upcoming songs with interactive controls")
    async def queue_cmd(self, interaction: discord.Interaction):
        manager = self.get_manager(interaction.guild)
        if not manager.current and not manager.queue:
            await interaction.response.send_message("📭 Queue is currently empty.", ephemeral=True)
            return

        embed = build_now_playing_embed(manager)
        view = MusicControlView(manager)
        await interaction.response.send_message(embed=embed, view=view)

    @app_commands.command(name="volume", description="Set playback volume between 1% and 200%")
    @app_commands.describe(percent="Volume percentage (1-200)")
    async def volume_cmd(self, interaction: discord.Interaction, percent: app_commands.Range[int, 1, 200]):
        manager = self.get_manager(interaction.guild)
        manager.set_volume(percent)
        await interaction.response.send_message(f"🔊 Volume adjusted to **{percent}%**")

    @app_commands.command(name="loop", description="Configure loop mode")
    @app_commands.describe(mode="Choose: off, track, or queue")
    async def loop_cmd(self, interaction: discord.Interaction, mode: Literal["off", "track", "queue"]):
        manager = self.get_manager(interaction.guild)
        manager.loop_mode = LoopMode(mode)
        await interaction.response.send_message(f"🔁 Loop mode set to: **{mode.title()}**")

    @app_commands.command(name="health", description="Display real-time system and bot health metrics")
    async def health(self, interaction: discord.Interaction):
        uptime_sec = int(time.time() - self.bot_start_time)
        uptime_str = str(datetime.timedelta(seconds=uptime_sec))

        process = psutil.Process(os.getpid())
        rss_mb = process.memory_info().rss / (1024 * 1024)
        cpu_pct = process.cpu_percent(interval=None)

        voice_sessions = len(self.bot.voice_clients)
        cookies_exist = os.path.exists("cookies/cookies.txt") and os.path.getsize("cookies/cookies.txt") > 100

        embed = discord.Embed(title="Bot Health & Telemetry", color=discord.Color.teal())
        embed.add_field(name="Uptime", value=uptime_str, inline=True)
        embed.add_field(name="RAM Usage", value=f"{rss_mb:.1f} MB", inline=True)
        embed.add_field(name="CPU Usage", value=f"{cpu_pct:.1f}%", inline=True)
        embed.add_field(name="Active Voice Sessions", value=str(voice_sessions), inline=True)
        embed.add_field(name="Gateway Latency", value=f"{round(self.bot.latency * 1000, 1)} ms", inline=True)
        embed.add_field(name="Cookies Auth", value="✅ Loaded" if cookies_exist else "⚠️ Unauthenticated", inline=True)
        embed.add_field(name="Python Version", value=platform.python_version(), inline=True)
        embed.add_field(name="discord.py Version", value=discord.__version__, inline=True)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="debug_logs", description="View recent diagnostic error traces from logs/error_traces.json")
    async def debug_logs(self, interaction: discord.Interaction):
        if not ERROR_TRACES_FILE.exists() or os.path.getsize(ERROR_TRACES_FILE) == 0:
            await interaction.response.send_message("✅ No error traces recorded. System running smoothly!", ephemeral=True)
            return

        traces = []
        with open(ERROR_TRACES_FILE, "r", encoding="utf-8") as f:
            for line in f:
                if line.strip():
                    try:
                        traces.append(json.loads(line.strip()))
                    except Exception:
                        pass

        if not traces:
            await interaction.response.send_message("✅ No error traces recorded.", ephemeral=True)
            return

        embed = discord.Embed(title=f"Diagnostic Error Traces (Last {min(5, len(traces))})", color=discord.Color.red())
        for tr in traces[-5:]:
            field_name = f"[{tr.get('trace_id')}] {tr.get('source_platform', 'unknown').upper()} - {tr.get('exception_type')}"
            field_val = f"**Func:** `{tr.get('function')}:{tr.get('line_number')}`\n**Error:** `{tr.get('message', '')[:100]}`\n**Time:** `{tr.get('timestamp')}`"
            embed.add_field(name=field_name, value=field_val, inline=False)

        await interaction.response.send_message(embed=embed, ephemeral=True)

async def setup(bot: commands.Bot):
    await bot.add_cog(MusicCog(bot))
