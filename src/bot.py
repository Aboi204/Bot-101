import asyncio
import os
import sys
from pathlib import Path
import discord
from discord.ext import commands
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
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
