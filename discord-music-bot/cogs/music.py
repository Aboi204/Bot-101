import datetime
import os
import platform
import time
from typing import Dict, Literal, Optional

import discord
from discord import app_commands
from discord.ext import commands
import psutil

import config
from audio.player import GuildPlayer, LoopMode
from audio.resolver import AudioResolver
from utils.logger import log

def create_progress_bar(elapsed_sec: int, total_sec: int, bar_length: int = 16) -> str:
    """Generates a text progress bar: 🔘────────── 01:23 / 03:45"""
    if total_sec <= 0:
        return "🔘" + ("─" * bar_length) + " Live / Stream"
    progress = min(1.0, max(0.0, elapsed_sec / total_sec))
    filled_blocks = int(round(progress * bar_length))
    bar = "─" * filled_blocks + "🔘" + "─" * (bar_length - filled_blocks)

    def fmt(s: int) -> str:
        m, sec = divmod(s, 60)
        h, m = divmod(m, 60)
        return f"{h}:{m:02d}:{sec:02d}" if h > 0 else f"{m:02d}:{sec:02d}"

    return f"`{bar}` {fmt(elapsed_sec)} / {fmt(total_sec)}"

class MusicCog(commands.Cog, name="Music"):
    """Music playback, queue management, and audio diagnostics commands."""

    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.resolver = AudioResolver()
        self.players: Dict[int, GuildPlayer] = {}
        self.start_time = time.time()

    def get_player(self, guild: discord.Guild) -> GuildPlayer:
        if guild.id not in self.players:
            self.players[guild.id] = GuildPlayer(self.bot, guild)
        return self.players[guild.id]

    async def _ensure_voice(self, interaction: discord.Interaction) -> Optional[discord.VoiceClient]:
        """Ensures the invoking user and bot are in a voice channel."""
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message("❌ You must be connected to a voice channel to use this command.", ephemeral=True)
            return None

        user_channel = interaction.user.voice.channel
        voice_client: Optional[discord.VoiceClient] = interaction.guild.voice_client

        if voice_client is None:
            voice_client = await user_channel.connect()
            log.info(f"Connected to voice channel {user_channel.name} in {interaction.guild.name}", extra={"event": "voice_connect", "guild_id": interaction.guild.id})
        elif voice_client.channel != user_channel:
            await voice_client.move_to(user_channel)

        return voice_client

    @app_commands.command(name="play", description="Play a song or playlist from YouTube, SoundCloud, or Spotify")
    @app_commands.describe(query="Song title, YouTube/SoundCloud URL, or Spotify track link")
    async def play(self, interaction: discord.Interaction, query: str):
        await interaction.response.defer()

        voice_client = await self._ensure_voice(interaction)
        if not voice_client:
            return

        player = self.get_player(interaction.guild)
        player.voice_client = voice_client
        player.text_channel = interaction.channel

        try:
            tracks = await self.resolver.resolve(query, user=interaction.user.display_name)
        except Exception as e:
            await interaction.followup.send(f"❌ Failed to extract audio: {e}")
            return

        if not tracks:
            await interaction.followup.send("❌ No playable audio found for that search or URL.")
            return

        if len(player.queue) + len(tracks) > config.MAX_QUEUE_SIZE:
            await interaction.followup.send(f"❌ Queue limit reached ({config.MAX_QUEUE_SIZE} tracks max).")
            return

        for track in tracks:
            player.queue.append(track)

        player.start_worker()

        if len(tracks) == 1:
            track = tracks[0]
            embed = discord.Embed(
                title="Added to Queue",
                description=f"[{track.title}]({track.webpage_url})",
                color=discord.Color.green()
            )
            embed.add_field(name="Duration", value=track.formatted_duration, inline=True)
            embed.add_field(name="Position in Queue", value=str(len(player.queue)), inline=True)
            if track.thumbnail:
                embed.set_thumbnail(url=track.thumbnail)
            await interaction.followup.send(embed=embed)
        else:
            embed = discord.Embed(
                title="Playlist Queued",
                description=f"Added **{len(tracks)}** songs to the queue.",
                color=discord.Color.green()
            )
            await interaction.followup.send(embed=embed)

    @app_commands.command(name="pause", description="Pause current song playback")
    async def pause(self, interaction: discord.Interaction):
        player = self.get_player(interaction.guild)
        if not player.is_playing:
            await interaction.response.send_message("❌ Nothing is currently playing.", ephemeral=True)
            return

        player.pause()
        await interaction.response.send_message("⏸️ Playback paused.")

    @app_commands.command(name="resume", description="Resume paused song playback")
    async def resume(self, interaction: discord.Interaction):
        player = self.get_player(interaction.guild)
        if not player.is_paused:
            await interaction.response.send_message("❌ Audio is not paused.", ephemeral=True)
            return

        player.resume()
        await interaction.response.send_message("▶️ Playback resumed.")

    @app_commands.command(name="skip", description="Skip to the next song in the queue")
    async def skip(self, interaction: discord.Interaction):
        player = self.get_player(interaction.guild)
        if not player.current:
            await interaction.response.send_message("❌ Nothing is currently playing.", ephemeral=True)
            return

        skipped_title = player.current.title
        player.skip()
        await interaction.response.send_message(f"⏭️ Skipped: **{skipped_title}**")

    @app_commands.command(name="stop", description="Stop playback and clear the song queue")
    async def stop(self, interaction: discord.Interaction):
        player = self.get_player(interaction.guild)
        player.stop()
        await interaction.response.send_message("⏹️ Playback stopped and queue cleared.")

    @app_commands.command(name="nowplaying", description="Show detailed information about the currently playing track")
    async def nowplaying(self, interaction: discord.Interaction):
        player = self.get_player(interaction.guild)
        if not player.current:
            await interaction.response.send_message("❌ Nothing is currently playing.", ephemeral=True)
            return

        track = player.current
        elapsed = player.elapsed_seconds
        bar = create_progress_bar(elapsed, track.duration)

        embed = discord.Embed(
            title="Now Playing",
            description=f"[{track.title}]({track.webpage_url})\n\n{bar}",
            color=discord.Color.blurple()
        )
        embed.add_field(name="Uploader", value=track.uploader, inline=True)
        embed.add_field(name="Requested By", value=track.requested_by or "Unknown", inline=True)
        embed.add_field(name="Loop Mode", value=player.loop_mode.value.title(), inline=True)
        embed.add_field(name="Volume", value=f"{int(player.volume * 100)}%", inline=True)
        embed.add_field(name="Extractor", value=track.extractor, inline=True)

        if track.thumbnail:
            embed.set_thumbnail(url=track.thumbnail)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="queue", description="Display the upcoming songs in the queue")
    async def queue_cmd(self, interaction: discord.Interaction):
        player = self.get_player(interaction.guild)
        if not player.current and not player.queue:
            await interaction.response.send_message("📭 The queue is currently empty.", ephemeral=True)
            return

        embed = discord.Embed(title=f"Queue for {interaction.guild.name}", color=discord.Color.blue())
        if player.current:
            embed.add_field(
                name="Currently Playing",
                value=f"🎶 [{player.current.title}]({player.current.webpage_url}) ({player.current.formatted_duration})",
                inline=False
            )

        if player.queue:
            queue_list = []
            for idx, track in enumerate(list(player.queue)[:10], start=1):
                queue_list.append(f"`{idx}.` [{track.title}]({track.webpage_url}) - `{track.formatted_duration}`")
            
            queue_str = "\n".join(queue_list)
            if len(player.queue) > 10:
                queue_str += f"\n*...and {len(player.queue) - 10} more track(s)*"
            
            embed.add_field(name=f"Upcoming Tracks ({len(player.queue)})", value=queue_str, inline=False)
        else:
            embed.add_field(name="Upcoming Tracks", value="No upcoming songs queued.", inline=False)

        await interaction.response.send_message(embed=embed)

    @app_commands.command(name="volume", description="Set playback volume (1% - 150%)")
    @app_commands.describe(percent="Volume percentage between 1 and 150")
    async def volume_cmd(self, interaction: discord.Interaction, percent: app_commands.Range[int, 1, 150]):
        player = self.get_player(interaction.guild)
        float_vol = percent / 100.0
        player.set_volume(float_vol)
        await interaction.response.send_message(f"🔊 Volume set to **{percent}%**")

    @app_commands.command(name="loop", description="Toggle loop mode (off, track, or entire queue)")
    @app_commands.describe(mode="Choose loop mode")
    async def loop_cmd(self, interaction: discord.Interaction, mode: Literal["off", "track", "queue"]):
        player = self.get_player(interaction.guild)
        player.loop_mode = LoopMode(mode)
        await interaction.response.send_message(f"🔁 Loop mode set to: **{mode.title()}**")

    @app_commands.command(name="leave", description="Disconnect the bot from the voice channel")
    async def leave_cmd(self, interaction: discord.Interaction):
        player = self.get_player(interaction.guild)
        await player.cleanup()
        await interaction.response.send_message("👋 Disconnected and cleared session.")

    @app_commands.command(name="diagnostics", description="View bot runtime diagnostics, system telemetry, and voice stats")
    async def diagnostics(self, interaction: discord.Interaction):
        uptime_sec = int(time.time() - self.start_time)
        uptime_str = str(datetime.timedelta(seconds=uptime_sec))

        process = psutil.Process(os.getpid())
        mem_info = process.memory_info()
        mem_mb = mem_info.rss / (1024 * 1024)
        cpu_pct = process.cpu_percent(interval=None)

        voice_clients_count = len(self.bot.voice_clients)
        cookie_status = "✅ Loaded" if os.path.exists(config.COOKIE_FILE) else "⚠️ Not Found"

        embed = discord.Embed(title="Bot Diagnostic Telemetry", color=discord.Color.gold())
        embed.add_field(name="Uptime", value=uptime_str, inline=True)
        embed.add_field(name="Memory (RSS)", value=f"{mem_mb:.1f} MB", inline=True)
        embed.add_field(name="CPU Usage", value=f"{cpu_pct:.1f}%", inline=True)
        embed.add_field(name="Active Voice Sessions", value=str(voice_clients_count), inline=True)
        embed.add_field(name="Discord Gateway Ping", value=f"{round(self.bot.latency * 1000, 1)} ms", inline=True)
        embed.add_field(name="YouTube Auth Cookies", value=cookie_status, inline=True)
        embed.add_field(name="Python Version", value=platform.python_version(), inline=True)
        embed.add_field(name="discord.py Version", value=discord.__version__, inline=True)
        embed.add_field(name="OS / Platform", value=f"{platform.system()} {platform.release()}", inline=True)

        await interaction.response.send_message(embed=embed)

async def setup(bot: commands.Bot):
    await bot.add_cog(MusicCog(bot))
