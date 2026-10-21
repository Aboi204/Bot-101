import random
from typing import Optional
import discord

def create_progress_bar(elapsed_sec: int, total_sec: int, length: int = 14) -> str:
    if total_sec <= 0:
        return "🔘" + "▬" * (length - 1)
    progress = min(1.0, max(0.0, elapsed_sec / total_sec))
    filled_length = int(round(length * progress))
    bar = "▬" * max(0, filled_length - 1) + "🔘" + "▬" * max(0, length - filled_length)
    return bar

def build_now_playing_embed(manager) -> discord.Embed:
    track = manager.current
    if not track:
        embed = discord.Embed(
            title="⏹️ Playback Stopped",
            description="No track is currently playing. Use `/play` to add music to the queue!",
            color=discord.Color.dark_gray()
        )
        return embed

    status_str = "⏸️ Paused" if manager.is_paused else "▶️ Playing"

    embed = discord.Embed(
        title="🎶 Now Playing",
        description=f"[{track.title}]({track.webpage_url})",
        color=discord.Color.blurple() if not manager.is_paused else discord.Color.orange()
    )

    embed.add_field(name="Status", value=status_str, inline=True)
    embed.add_field(name="Duration", value=track.formatted_duration, inline=True)
    embed.add_field(name="Volume", value=f"{int(round(manager.volume * 100))}%", inline=True)
    embed.add_field(name="Platform", value=track.source_platform.replace("_", " ").title(), inline=True)
    embed.add_field(name="Loop Mode", value=manager.loop_mode.value.title(), inline=True)
    embed.add_field(name="Uploader", value=track.uploader[:35] if track.uploader else "Unknown", inline=True)

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

    embed.set_footer(text=f"Trace-ID: {track.trace_id} • Studio Loudness (EBU R128)")
    if track.thumbnail:
        embed.set_thumbnail(url=track.thumbnail)

    return embed

class MusicControlView(discord.ui.View):
    """
    Feature-complete, modern interactive message buttons:
    Row 0: [ ⏮️ Prev ] [ ⏯️ Pause/Resume ] [ ⏭️ Next ] [ 🔁 Replay ] [ ⏹️ Stop ]
    Row 1: [ 🔉 Vol -15% ] [ 🔊 Vol +15% ] [ 🔀 Shuffle ] [ 🔄 Loop ] [ 📜 Queue ]
    """

    def __init__(self, manager):
        super().__init__(timeout=None)
        self.manager = manager
        self.message: Optional[discord.Message] = None
        self._update_button_states()

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        # Allow queue view for all members
        if interaction.data and interaction.data.get("custom_id") == "btn_queue":
            return True

        # Require caller to be in the same voice channel
        if not interaction.user.voice or not interaction.user.voice.channel:
            await interaction.response.send_message("❌ يجب أن تكون متواجداً في الروم الصوتي للتحكم في التشغيل.", ephemeral=True)
            return False

        if self.manager.voice_client and interaction.user.voice.channel != self.manager.voice_client.channel:
            await interaction.response.send_message("❌ يجب أن تكون في نفس الروم الصوتي مع البوت.", ephemeral=True)
            return False

        return True

    async def on_error(self, interaction: discord.Interaction, error: Exception, item: discord.ui.Item) -> None:
        if not interaction.response.is_done():
            try:
                await interaction.response.send_message("⚠️ تعذر استكمال استجابة الزر، يرجى المحاولة مرة أخرى.", ephemeral=True)
            except Exception:
                pass

    def _find_button(self, custom_id: str) -> Optional[discord.ui.Button]:
        for child in self.children:
            if isinstance(child, discord.ui.Button) and child.custom_id == custom_id:
                return child
        return None

    def _update_button_states(self):
        # Pause/Resume toggle button
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

        # Previous button state
        prev_btn = self._find_button("btn_prev")
        if prev_btn:
            prev_btn.disabled = len(self.manager.history) == 0

        # Loop mode button label & emoji
        loop_btn = self._find_button("btn_loop")
        if loop_btn:
            mode = self.manager.loop_mode.value
            if mode == "track":
                loop_btn.label = "Track"
                loop_btn.emoji = "🔂"
                loop_btn.style = discord.ButtonStyle.success
            elif mode == "queue":
                loop_btn.label = "Queue"
                loop_btn.emoji = "🔁"
                loop_btn.style = discord.ButtonStyle.primary
            else:
                loop_btn.label = "Off"
                loop_btn.emoji = "➡️"
                loop_btn.style = discord.ButtonStyle.secondary

        # Volume buttons disabled if at boundaries
        vol_down = self._find_button("btn_vol_down")
        if vol_down:
            vol_down.disabled = self.manager.volume <= 0.15

        vol_up = self._find_button("btn_vol_up")
        if vol_up:
            vol_up.disabled = self.manager.volume >= 2.0

    # ================= ROW 0: CORE PLAYBACK CONTROLS =================

    @discord.ui.button(label="Previous", style=discord.ButtonStyle.secondary, emoji="⏮️", custom_id="btn_prev", row=0)
    async def prev_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.manager.history:
            await interaction.response.send_message("⚠️ No previous tracks in history.", ephemeral=True)
            return

        await interaction.response.defer()
        success = self.manager.play_previous()
        if not success:
            await interaction.followup.send("❌ Failed to play previous track.", ephemeral=True)

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

    @discord.ui.button(label="Skip", style=discord.ButtonStyle.secondary, emoji="⏭️", custom_id="btn_next", row=0)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.manager.current:
            await interaction.response.send_message("❌ Nothing is currently playing.", ephemeral=True)
            return

        await interaction.response.defer()
        self.manager.skip()

    @discord.ui.button(label="Replay", style=discord.ButtonStyle.secondary, emoji="🔁", custom_id="btn_replay", row=0)
    async def replay_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.manager.current:
            await interaction.response.send_message("❌ Nothing is currently playing.", ephemeral=True)
            return

        await interaction.response.defer()
        success = self.manager.replay_current()
        if not success:
            await interaction.followup.send("❌ Failed to replay track.", ephemeral=True)

    @discord.ui.button(label="Stop", style=discord.ButtonStyle.danger, emoji="⏹️", custom_id="btn_stop", row=0)
    async def stop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        self.manager.stop()
        for child in self.children:
            child.disabled = True
        embed = build_now_playing_embed(self.manager)
        await interaction.response.edit_message(embed=embed, view=self)

    # ================= ROW 1: VOLUME & MIX CONTROLS =================

    @discord.ui.button(label="-15%", style=discord.ButtonStyle.secondary, emoji="🔉", custom_id="btn_vol_down", row=1)
    async def vol_down_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        new_vol = self.manager.adjust_volume(-15)
        self._update_button_states()
        embed = build_now_playing_embed(self.manager)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="+15%", style=discord.ButtonStyle.secondary, emoji="🔊", custom_id="btn_vol_up", row=1)
    async def vol_up_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        new_vol = self.manager.adjust_volume(+15)
        self._update_button_states()
        embed = build_now_playing_embed(self.manager)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Shuffle", style=discord.ButtonStyle.secondary, emoji="🔀", custom_id="btn_shuffle", row=1)
    async def shuffle_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        count = self.manager.shuffle_queue()
        if count == 0:
            await interaction.response.send_message("⚠️ Queue is empty, nothing to shuffle.", ephemeral=True)
            return

        embed = build_now_playing_embed(self.manager)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Loop", style=discord.ButtonStyle.secondary, emoji="🔄", custom_id="btn_loop", row=1)
    async def loop_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        mode = self.manager.cycle_loop_mode()
        self._update_button_states()
        embed = build_now_playing_embed(self.manager)
        await interaction.response.edit_message(embed=embed, view=self)

    @discord.ui.button(label="Queue", style=discord.ButtonStyle.secondary, emoji="📜", custom_id="btn_queue", row=1)
    async def queue_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        if not self.manager.queue and not self.manager.current:
            await interaction.response.send_message("📭 Queue is completely empty.", ephemeral=True)
            return

        lines = []
        if self.manager.current:
            lines.append(f"**Now Playing:** [{self.manager.current.title}]({self.manager.current.webpage_url}) (`{self.manager.current.formatted_duration}`)\n")
        
        if self.manager.queue:
            lines.append("**Upcoming Tracks:**")
            for idx, track in enumerate(list(self.manager.queue)[:10], start=1):
                lines.append(f"`{idx}.` [{track.title[:50]}]({track.webpage_url}) (`{track.formatted_duration}`)")
            if len(self.manager.queue) > 10:
                lines.append(f"\n*...and {len(self.manager.queue) - 10} more*")

        q_embed = discord.Embed(
            title="📜 Current Playback Queue",
            description="\n".join(lines),
            color=discord.Color.blurple()
        )
        await interaction.response.send_message(embed=q_embed, ephemeral=True)
