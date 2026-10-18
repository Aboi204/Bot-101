import asyncio
import os
import sys
import discord
from discord.ext import commands

import config
from utils.logger import log

class MusicBot(commands.Bot):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True

        super().__init__(
            command_prefix=config.BOT_PREFIX,
            intents=intents,
            help_command=None
        )

    async def setup_hook(self):
        # Load cogs
        log.info("Loading extensions/cogs...")
        try:
            await self.load_extension("cogs.music")
            log.info("Successfully loaded 'cogs.music'")
        except Exception as e:
            log.critical(f"Failed to load 'cogs.music': {e}", exc_info=True)
            sys.exit(1)

        # Sync application commands to Discord
        log.info("Synchronizing application slash commands with Discord...")
        try:
            synced = await self.tree.sync()
            log.info(f"Synced {len(synced)} application slash commands.")
        except Exception as e:
            log.error(f"Failed to sync application commands: {e}", exc_info=True)

    async def on_ready(self):
        log.info(
            f"Bot logged in as {self.user.name}#{self.user.discriminator} (ID: {self.user.id})",
            extra={"event": "bot_ready", "metadata": {"guild_count": len(self.guilds)}}
        )
        await self.change_presence(
            activity=discord.Activity(type=discord.ActivityType.listening, name="/play")
        )

    async def on_voice_state_update(self, member: discord.Member, before: discord.VoiceState, after: discord.VoiceState):
        """Cleanup player if bot is disconnected by admin or channel deletion."""
        if member.id == self.user.id and before.channel is not None and after.channel is None:
            log.warning(
                f"Bot was disconnected from voice channel in guild {member.guild.name} ({member.guild.id})",
                extra={"event": "voice_disconnect", "guild_id": member.guild.id}
            )
            music_cog = self.get_cog("Music")
            if music_cog and member.guild.id in music_cog.players:
                player = music_cog.players[member.guild.id]
                player.stop()

async def main():
    if not config.DISCORD_TOKEN or config.DISCORD_TOKEN == "your_discord_bot_token_here":
        log.critical("DISCORD_TOKEN is missing or not set in .env! Please set your bot token.")
        print("\n[ERROR] DISCORD_TOKEN is missing!")
        print("Please edit discord-music-bot/.env and provide your Discord bot token.")
        sys.exit(1)

    bot = MusicBot()
    async with bot:
        await bot.start(config.DISCORD_TOKEN)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Bot shutting down via KeyboardInterrupt.")
