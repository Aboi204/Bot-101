import time
from typing import Optional
import discord

def create_progress_bar(elapsed_sec: int, total_sec: int, bar_length: int = 14) -> str:
    if total_sec <= 0:
        return "🔘" + ("─" * bar_length) + " Live / Unknown"
    progress = min(1.0, max(0.0, elapsed_sec / total_sec))
    filled_blocks = int(round(progress * bar_length))
    bar = "─" * filled_blocks + "🔘" + "─" * (bar_length - filled_blocks)

    def fmt(s: int) -> str:
        m, sec = divmod(s, 60)
        h, m = divmod(m, 60)
        return f"{h}:{m:02d}:{sec:02d}" if h > 0 else f"{m:02d}:{sec:02d}"

    return f"`{bar}` {fmt(elapsed_sec)} / {fmt(total_sec)}"

def build_now_playing_embed(manager) -> discord.Embed:
    track = manager.current
    if not track:
        embed = discord.Embed(
            title="⏹️ Playback Stopped",
            description="No track is currently playing.",
            color=discord.Color.dark_gray()
        )
        return embed

    elapsed = manager.elapsed_seconds
    progress_bar = create_progress_bar(elapsed, track.duration)
    status_str = "⏸️ Paused" if manager.is_paused else "▶️ Playing"

    embed = discord.Embed(
        title="🎶 Now Playing",
        description=f"[{track.title}]({track.webpage_url})\n\n{progress_bar}",
        color=discord.Color.blurple() if not manager.is_paused else discord.Color.orange()
    )

    embed.add_field(name="Status", value=status_str, inline=True)
    embed.add_field(name="Source", value=track.source_platform.replace("_", " ").title(), inline=True)
    embed.add_field(name="Volume", value=f"{int(manager.volume * 100)}%", inline=True)
    embed.add_field(name="Uploader", value=track.uploader[:40] if track.uploader else "Unknown", inline=True)
    embed.add_field(name="Loop", value=manager.loop_mode.value.title(), inline=True)

    # Queue preview directly in the embed
    if manager.queue:
        queue_preview = []
        for idx, t in enumerate(list(manager.queue)[:3], start=1):
            queue_preview.append(f"`{idx}.` [{t.title[:45]}]({t.webpage_url}) (`{t.formatted_duration}`)")
        preview_text = "\n".join(queue_preview)
        if len(manager.queue) > 3:
            preview_text += f"\n*...and {len(manager.queue) - 3} more in queue*"
        embed.add_field(name=f"📜 Upcoming Queue ({len(manager.queue)})", value=preview_text, inline=False)
    else:
        embed.add_field(name="📜 Upcoming Queue", value="No upcoming songs queued.", inline=False)

    embed.set_footer(text=f"Trace-ID: {track.trace_id} • High Quality Direct Streaming")
    if track.thumbnail:
        embed.set_thumbnail(url=track.thumbnail)

    return embed

class MusicControlView(discord.ui.View):
    """
    Interactive message buttons for real-time player control:
    [ ⏮️ Previous ] [ ⏯️ Pause/Resume ] [ ⏭️ Next ] [ 🔁 Replay ] [ ⏹️ Stop ]
    """

    def __init__(self, manager):
        super().__init__(timeout=None)
        self.manager = manager
        self.message: Optional[discord.Message] = None
        self._update_button_states()

    def _find_button(self, custom_id: str) -> Optional[discord.ui.Button]:
        for child in self.children:
            if isinstance(child, discord.ui.Button) and child.custom_id == custom_id:
                return child
        return None

    def _update_button_states(self):
        pause_btn = self._find_button("btn_pause_resume")
        if pause_btn:
            if self.manager.is_paused:
                pause_btn.label = "Resume"
                pause_btn.style = discord.ButtonStyle.success
                pause_btn.emoji = "▶️"
            else:
                pause_btn.label = "Pause"
                pause_btn.style = discord.ButtonStyle.primary
                pause_btn.emoji = "⏸️"

        prev_btn = self._find_button("btn_prev")
        if prev_btn:
            prev_btn.disabled = len(self.manager.history) == 0

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.secondary, emoji="⏮️", custom_id="btn_prev", row=0)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.manager.history:
            await interaction.response.send_message("⚠️ No previous tracks in history.", ephemeral=True)
            return

        success = self.manager.play_previous()
        if success:
            self._update_button_states()
            embed = build_now_playing_embed(self.manager)
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.send_message("❌ Failed to play previous track.", ephemeral=True)

    @discord.ui.button(label="Pause", style=discord.ButtonStyle.primary, emoji="⏸️", custom_id="btn_pause_resume", row=0)
    async def pause_resume_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if self.manager.is_paused:
            self.manager.resume()
        elif self.manager.is_playing:
            self.manager.pause()
        else:
            await interaction.response.send_message("❌ Nothing is currently active.", ephemeral=True)
            return

        self._update_button_states()
        embed = build_now_playing_embed(self.manager)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Next", style=discord.ButtonStyle.secondary, emoji="⏭️", custom_id="btn_next", row=0)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.manager.current:
            await interaction.response.send_message("❌ Nothing is currently playing.", ephemeral=True)
            return

        self.manager.skip()
        self._update_button_states()
        embed = build_now_playing_embed(self.manager)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Replay", style=discord.ButtonStyle.secondary, emoji="🔁", custom_id="btn_replay", row=0)
    async def replay_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.manager.current:
            await interaction.response.send_message("❌ Nothing is currently playing.", ephemeral=True)
            return

        success = self.manager.replay_current()
        if success:
            self._update_button_states()
            embed = build_now_playing_embed(self.manager)
            await interaction.response.edit_message(embed=embed, view=self)
        else:
            await interaction.response.send_message("❌ Failed to replay track.", ephemeral=True)

    @discord.ui.button(label="Stop", style=discord.ButtonStyle.danger, emoji="⏹️", custom_id="btn_stop", row=0)
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.manager.stop()
        for child in self.children:
            child.disabled = True
        embed = build_now_playing_embed(self.manager)
        await interaction.response.edit_message(embed=embed, view=self)
