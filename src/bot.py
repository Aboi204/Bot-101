import asyncio
import os
import sys
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import discord
from discord.ext import commands
from dotenv import load_dotenv

load_dotenv(dotenv_path=BASE_DIR / ".env")

from src.utils.logger import log
from src.utils.keep_alive import KeepAliveServer

class AdvancedMusicBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        intents.members = True

        super().__init__(
            command_prefix=os.getenv("BOT_PREFIX", "!"),
            intents=intents,
            help_command=None
        )
        self.health_server: KeepAliveServer = None
        self.log_channel_name = os.getenv("LOG_CHANNEL_NAME", "bot-logs").lower().strip("#")

    async def setup_hook(self):
        # Start Keep-Alive Health Server
        port = int(os.getenv("PORT", 8000))
        self.health_server = KeepAliveServer(bot=self, port=port)
        try:
            await self.health_server.start()
        except Exception as e:
            log.warning(f"Could not start keep-alive server on port {port}: {e}")

        # Load Music Cog
        log.info("Loading cog: src.cogs.music...")
        try:
            await self.load_extension("src.cogs.music")
            log.info("Successfully loaded src.cogs.music")
        except Exception as e:
            log.critical(f"Failed to load src.cogs.music: {e}", exc_info=True)
            sys.exit(1)

        # Synchronize Application Slash Commands
        log.info("Synchronizing application slash commands with Discord gateway...")
        try:
            synced = await self.tree.sync()
            log.info(f"Successfully synced {len(synced)} application slash commands.")
        except Exception as e:
            log.error(f"Error synchronizing slash commands: {e}", exc_info=True)

    async def on_ready(self):
        log.info(
            f"Bot logged in as {self.user.name}#{self.user.discriminator} (ID: {self.user.id}) | Connected Guilds: {len(self.guilds)}",
            extra={"trace_id": "TRC-READY"}
        )
        await self.change_presence(
            activity=discord.Activity(
                type=discord.ActivityType.listening,
                name="/play (YouTube, SoundCloud, FB, Telegram, Drive)"
            )
        )

        # Send startup notification to designated log channel (e.g. #bot-logs)
        for guild in self.guilds:
            target_channel = discord.utils.find(
                lambda c: c.name.lower() == self.log_channel_name,
                guild.text_channels
            )
            if target_channel and target_channel.permissions_for(guild.me).send_messages:
                try:
                    embed = discord.Embed(
                        title="🚀 Discord Music Bot Online & Ready",
                        description="Multi-source audio stream resolver & self-healing voice engine are fully operational.",
                        color=discord.Color.green()
                    )
                    embed.add_field(
                        name="Supported Sources (100% Verified)",
                        value="• **YouTube** (Videos, Shorts, Playlists, Livestreams)\n• **SoundCloud** (Tracks, Mixes)\n• **Facebook** (Videos, Reels)\n• **Telegram** (Posts, Audio Embeds)\n• **Google Drive** (Direct stream bypass)",
                        inline=False
                    )
                    embed.add_field(
                        name="Available Slash Commands",
                        value="`/play`, `/pause`, `/resume`, `/skip`, `/stop`, `/queue`, `/nowplaying`, `/volume`, `/loop`, `/health`, `/debug_logs`",
                        inline=False
                    )
                    embed.add_field(
                        name="Telemetry & Watchdog",
                        value=f"• Gateway Latency: `{round(self.latency * 1000, 1)} ms`\n• Keep-Alive HTTP: `http://0.0.0.0:{os.getenv('PORT', 8000)}/health`\n• Auto Stream Resume: `-ss` dynamic seek active",
                        inline=False
                    )
                    embed.set_footer(text=f"Bot ID: {self.user.id} • Channel: #{target_channel.name}")
                    await target_channel.send(embed=embed)
                    log.info(f"Sent startup message to #{target_channel.name} in guild '{guild.name}'")
                except Exception as e:
                    log.warning(f"Could not send startup embed to #{target_channel.name}: {e}")

    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        if member.id == self.user.id and before.channel is not None and after.channel is None:
            log.warning(f"Bot was disconnected from voice channel in guild {member.guild.name} ({member.guild.id})")
            cog = self.get_cog("Music")
            if cog and member.guild.id in cog.managers:
                cog.managers[member.guild.id].stop()

    async def close(self):
        if self.health_server:
            await self.health_server.stop()
        await super().close()

async def run_bot():
    token = os.getenv("DISCORD_TOKEN", "").strip()
    if not token or token == "your_discord_bot_token_here":
        log.critical("DISCORD_TOKEN is missing in .env! Configure your token before starting.")
        print("\n[ERROR] DISCORD_TOKEN is missing in .env!")
        print("Please configure DISCORD_TOKEN in .env\n")
        return

    bot = AdvancedMusicBot()
    async with bot:
        await bot.start(token)

if __name__ == "__main__":
    try:
        asyncio.run(run_bot())
    except KeyboardInterrupt:
        log.info("Bot shutting down gracefully via KeyboardInterrupt.")
