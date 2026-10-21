import asyncio
import io
import os
import queue
import sys
import threading
import time
from pathlib import Path
import tkinter as tk
from tkinter import ttk

if sys.stdout is None:
    sys.stdout = io.StringIO()
if sys.stderr is None:
    sys.stderr = io.StringIO()

if getattr(sys, "frozen", False):
    BASE_DIR = Path(sys._MEIPASS)
    APP_DIR = Path(sys.executable).resolve().parent
else:
    BASE_DIR = Path(__file__).resolve().parent.parent
    APP_DIR = BASE_DIR

if str(BASE_DIR) not in sys.path:
    sys.path.insert(0, str(BASE_DIR))

import discord
from dotenv import load_dotenv

# Load .env
for env_candidate in [APP_DIR / ".env", BASE_DIR / ".env"]:
    if env_candidate.is_file():
        load_dotenv(dotenv_path=env_candidate, override=True)
        break

from src.bot import AdvancedMusicBot
from src.utils.logger import log, add_gui_log_handler, BotActivityFormatter

# Color Palette (Discord Dark Theme)
BG_DARK = "#1e1f22"         # Main window background
PANEL_BG = "#2b2d31"        # Card / panel background
CONSOLE_BG = "#111214"      # Monospace log box
BORDER_COLOR = "#383a40"
TEXT_WHITE = "#ffffff"
TEXT_MUTED = "#949ba4"
DISCORD_GREEN = "#23a55a"   # Online / Start
DISCORD_RED = "#da373c"     # Offline / Disconnect
DISCORD_BLURPLE = "#5865f2"
HOVER_GREEN = "#1f8b4c"
HOVER_RED = "#ba2e34"

class BotThreadController:
    """Manages the lifecycle of the Discord bot on an asyncio event loop in a background thread."""

    def __init__(self, log_queue: queue.Queue):
        self.log_queue = log_queue
        self.bot: AdvancedMusicBot = None
        self.loop: asyncio.AbstractEventLoop = None
        self.thread: threading.Thread = None
        self.is_running = False
        self.is_connected = False
        self.status_listeners = []

    def add_status_listener(self, callback):
        self.status_listeners.append(callback)

    def _notify_status(self, status: str, details: dict = None):
        for cb in self.status_listeners:
            try:
                cb(status, details or {})
            except Exception:
                pass

    def start(self):
        if self.is_running:
            return
        self.is_running = True
        self.thread = threading.Thread(target=self._run_event_loop, daemon=True)
        self.thread.start()

    def _run_event_loop(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)

        token = os.getenv("DISCORD_TOKEN", "").strip()
        if not token or token == "your_discord_bot_token_here":
            self.log_queue.put(("[CRITICAL] DISCORD_TOKEN is missing in .env! Configure your token in .env", "ERROR"))
            self.is_running = False
            self._notify_status("OFFLINE", {"error": "Missing Token"})
            return

        self.bot = AdvancedMusicBot()

        # Hook on_ready to notify UI
        orig_on_ready = self.bot.on_ready

        async def _gui_on_ready():
            await orig_on_ready()
            self.is_connected = True
            details = {
                "name": str(self.bot.user),
                "guilds": len(self.bot.guilds),
                "ping": round(self.bot.latency * 1000, 1) if self.bot.latency else 0,
            }
            self._notify_status("ONLINE", details)

        self.bot.on_ready = _gui_on_ready

        try:
            self._notify_status("CONNECTING")
            self.loop.run_until_complete(self.bot.start(token))
        except asyncio.CancelledError:
            pass
        except Exception as e:
            self.log_queue.put((f"[ERROR] Bot disconnected: {e}", "ERROR"))
        finally:
            self.is_connected = False
            self.is_running = False
            self._notify_status("OFFLINE")
            try:
                self.loop.run_until_complete(self.loop.shutdown_asyncgens())
            except Exception:
                pass
            self.loop.close()

    def disconnect(self):
        if not self.is_running or not self.bot or not self.loop:
            return

        self._notify_status("DISCONNECTING")
        self.log_queue.put(("[INFO] Disconnecting bot from Discord gateway...", "INFO"))

        async def _shutdown():
            # Disconnect all voice sessions cleanly
            for vc in list(self.bot.voice_clients):
                try:
                    await vc.disconnect(force=True)
                except Exception:
                    pass
            await self.bot.close()

        if self.loop.is_running():
            asyncio.run_coroutine_threadsafe(_shutdown(), self.loop)

class Bot101GUI:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("Bot 101")
        self.root.geometry("600x650")
        self.root.minsize(540, 580)
        self.root.configure(bg=BG_DARK)

        # Center on screen
        self._center_window(600, 650)

        # Log queue
        self.log_queue = queue.Queue()

        # Bot controller
        self.controller = BotThreadController(self.log_queue)
        self.controller.add_status_listener(self._on_bot_status_changed)

        # Hook logger output
        def _gui_log_handler(msg: str, levelno: int):
            level_name = "INFO"
            if levelno >= 40:
                level_name = "ERROR"
            elif levelno >= 30:
                level_name = "WARNING"
            self.log_queue.put((msg, level_name))

        add_gui_log_handler(_gui_log_handler)

        # Load Icon
        self._set_window_icon()

        # Build UI layout
        self._build_header()
        self._build_status_card()
        self._build_controls()
        self._build_log_console()
        self._build_footer()

        # Periodic tasks
        self.root.after(100, self._process_log_queue)
        self.root.after(2000, self._periodic_stats_update)

        # Clean exit on close
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        # Auto-start bot on launch for maximum 1-click convenience
        self.root.after(400, self._start_bot_action)

    def _center_window(self, width: int, height: int):
        self.root.update_idletasks()
        sw = self.root.winfo_screenwidth()
        sh = self.root.winfo_screenheight()
        x = (sw - width) // 2
        y = (sh - height) // 2
        self.root.geometry(f"{width}x{height}+{x}+{y}")

    def _set_window_icon(self):
        icon_loaded = False
        for candidate in [
            APP_DIR / "assets" / "bot_icon.ico",
            BASE_DIR / "assets" / "bot_icon.ico",
        ]:
            if candidate.is_file():
                try:
                    self.root.iconbitmap(str(candidate))
                    icon_loaded = True
                    break
                except Exception:
                    pass

        # Also set iconphoto via PNG for taskbar and title bar compatibility
        for png_cand in [
            APP_DIR / "assets" / "discord_green.png",
            BASE_DIR / "assets" / "discord_green.png",
        ]:
            if png_cand.is_file():
                try:
                    from PIL import ImageTk, Image
                    pil_img = Image.open(png_cand)
                    self._app_icon_photo = ImageTk.PhotoImage(pil_img)
                    self.root.iconphoto(True, self._app_icon_photo)
                    break
                except Exception:
                    pass

    def _build_header(self):
        header_frame = tk.Frame(self.root, bg=BG_DARK, pady=12, padx=20)
        header_frame.pack(fill=tk.X)

        # Left branding block
        brand_frame = tk.Frame(header_frame, bg=BG_DARK)
        brand_frame.pack(side=tk.LEFT)

        # Load icon image for header
        self.header_icon_img = None
        for png_cand in [
            APP_DIR / "assets" / "discord_green.png",
            BASE_DIR / "assets" / "discord_green.png",
        ]:
            if png_cand.is_file():
                try:
                    from PIL import ImageTk, Image
                    img = Image.open(png_cand).resize((44, 44), Image.Resampling.LANCZOS)
                    self.header_icon_img = ImageTk.PhotoImage(img)
                    break
                except Exception:
                    pass

        if self.header_icon_img:
            icon_lbl = tk.Label(brand_frame, image=self.header_icon_img, bg=BG_DARK)
            icon_lbl.pack(side=tk.LEFT, padx=(0, 12))
        else:
            badge_canvas = tk.Canvas(brand_frame, width=42, height=42, bg=BG_DARK, highlightthickness=0)
            badge_canvas.pack(side=tk.LEFT, padx=(0, 12))
            badge_canvas.create_oval(3, 3, 39, 39, fill=DISCORD_GREEN, outline="")

        title_box = tk.Frame(brand_frame, bg=BG_DARK)
        title_box.pack(side=tk.LEFT)

        title_label = tk.Label(
            title_box,
            text="Bot 101",
            font=("Segoe UI", 18, "bold"),
            fg=TEXT_WHITE,
            bg=BG_DARK
        )
        title_label.pack(anchor="w")

        subtitle_label = tk.Label(
            title_box,
            text="Discord Music Assistant • Local Host",
            font=("Segoe UI", 9),
            fg=TEXT_MUTED,
            bg=BG_DARK
        )
        subtitle_label.pack(anchor="w")

        # Right status badge pill
        self.status_pill_frame = tk.Frame(header_frame, bg=BORDER_COLOR, padx=10, pady=4)
        self.status_pill_frame.pack(side=tk.RIGHT, pady=6)

        self.status_dot = tk.Canvas(self.status_pill_frame, width=12, height=12, bg=BORDER_COLOR, highlightthickness=0)
        self.status_dot.pack(side=tk.LEFT, padx=(0, 6))
        self.dot_item = self.status_dot.create_oval(2, 2, 10, 10, fill="#80848e", outline="")

        self.status_text_lbl = tk.Label(
            self.status_pill_frame,
            text="OFFLINE",
            font=("Segoe UI", 9, "bold"),
            fg=TEXT_MUTED,
            bg=BORDER_COLOR
        )
        self.status_text_lbl.pack(side=tk.LEFT)

    def _build_status_card(self):
        card = tk.Frame(self.root, bg=PANEL_BG, padx=16, pady=12, highlightthickness=1, highlightbackground=BORDER_COLOR)
        card.pack(fill=tk.X, padx=20, pady=(0, 12))

        # Grid of 4 telemetry metrics
        card.columnconfigure(0, weight=1)
        card.columnconfigure(1, weight=1)

        # Block 1: Bot Identity
        b1 = tk.Frame(card, bg=PANEL_BG)
        b1.grid(row=0, column=0, sticky="w", pady=4)
        tk.Label(b1, text="LOGGED IN AS", font=("Segoe UI", 8, "bold"), fg=TEXT_MUTED, bg=PANEL_BG).pack(anchor="w")
        self.tag_label = tk.Label(b1, text="Connecting...", font=("Segoe UI", 11, "bold"), fg=TEXT_WHITE, bg=PANEL_BG)
        self.tag_label.pack(anchor="w")

        # Block 2: Connected Servers
        b2 = tk.Frame(card, bg=PANEL_BG)
        b2.grid(row=0, column=1, sticky="w", pady=4)
        tk.Label(b2, text="SERVERS (GUILDS)", font=("Segoe UI", 8, "bold"), fg=TEXT_MUTED, bg=PANEL_BG).pack(anchor="w")
        self.guilds_label = tk.Label(b2, text="-", font=("Segoe UI", 11, "bold"), fg=TEXT_WHITE, bg=PANEL_BG)
        self.guilds_label.pack(anchor="w")

        # Block 3: Gateway Latency
        b3 = tk.Frame(card, bg=PANEL_BG)
        b3.grid(row=1, column=0, sticky="w", pady=4)
        tk.Label(b3, text="GATEWAY LATENCY", font=("Segoe UI", 8, "bold"), fg=TEXT_MUTED, bg=PANEL_BG).pack(anchor="w")
        self.ping_label = tk.Label(b3, text="-", font=("Segoe UI", 11, "bold"), fg=TEXT_WHITE, bg=PANEL_BG)
        self.ping_label.pack(anchor="w")

        # Block 4: Web Health Check
        b4 = tk.Frame(card, bg=PANEL_BG)
        b4.grid(row=1, column=1, sticky="w", pady=4)
        tk.Label(b4, text="KEEP-ALIVE HTTP", font=("Segoe UI", 8, "bold"), fg=TEXT_MUTED, bg=PANEL_BG).pack(anchor="w")
        port = os.getenv("PORT", "8000")
        self.web_label = tk.Label(b4, text=f"http://127.0.0.1:{port}/health", font=("Segoe UI", 10), fg=DISCORD_BLURPLE, bg=PANEL_BG)
        self.web_label.pack(anchor="w")

    def _build_controls(self):
        ctrl_frame = tk.Frame(self.root, bg=BG_DARK, padx=20)
        ctrl_frame.pack(fill=tk.X, pady=(0, 12))

        ctrl_frame.columnconfigure(0, weight=1)
        ctrl_frame.columnconfigure(1, weight=1)

        # Start Bot Button
        self.start_btn = tk.Button(
            ctrl_frame,
            text="▶  Start Bot",
            font=("Segoe UI", 11, "bold"),
            fg=TEXT_WHITE,
            bg=DISCORD_GREEN,
            activebackground=HOVER_GREEN,
            activeforeground=TEXT_WHITE,
            relief=tk.FLAT,
            cursor="hand2",
            padx=16,
            pady=8,
            command=self._start_bot_action
        )
        self.start_btn.grid(row=0, column=0, sticky="ew", padx=(0, 6))

        # Disconnect Bot Button
        self.disconnect_btn = tk.Button(
            ctrl_frame,
            text="⏹  Disconnect Bot",
            font=("Segoe UI", 11, "bold"),
            fg=TEXT_WHITE,
            bg=DISCORD_RED,
            activebackground=HOVER_RED,
            activeforeground=TEXT_WHITE,
            relief=tk.FLAT,
            cursor="hand2",
            padx=16,
            pady=8,
            state=tk.DISABLED,
            command=self._disconnect_bot_action
        )
        self.disconnect_btn.grid(row=0, column=1, sticky="ew", padx=(6, 0))

    def _build_log_console(self):
        log_header = tk.Frame(self.root, bg=BG_DARK, padx=20)
        log_header.pack(fill=tk.X, pady=(4, 4))

        tk.Label(
            log_header,
            text="DIAGNOSTIC & ACTIVITY LOGS",
            font=("Segoe UI", 8, "bold"),
            fg=TEXT_MUTED,
            bg=BG_DARK
        ).pack(side=tk.LEFT)

        clear_btn = tk.Button(
            log_header,
            text="Clear",
            font=("Segoe UI", 8),
            fg=TEXT_MUTED,
            bg=PANEL_BG,
            activebackground=BORDER_COLOR,
            activeforeground=TEXT_WHITE,
            relief=tk.FLAT,
            padx=8,
            pady=1,
            cursor="hand2",
            command=self._clear_logs
        )
        clear_btn.pack(side=tk.RIGHT)

        self.auto_scroll_var = tk.BooleanVar(value=True)
        auto_chk = tk.Checkbutton(
            log_header,
            text="Auto-scroll",
            variable=self.auto_scroll_var,
            font=("Segoe UI", 8),
            fg=TEXT_MUTED,
            bg=BG_DARK,
            activebackground=BG_DARK,
            activeforeground=TEXT_WHITE,
            selectcolor=PANEL_BG,
            highlightthickness=0
        )
        auto_chk.pack(side=tk.RIGHT, padx=8)

        # Log Text Box
        console_frame = tk.Frame(self.root, bg=CONSOLE_BG, padx=2, pady=2, highlightthickness=1, highlightbackground=BORDER_COLOR)
        console_frame.pack(fill=tk.BOTH, expand=True, padx=20, pady=(0, 10))

        self.log_text = tk.Text(
            console_frame,
            bg=CONSOLE_BG,
            fg="#dbdee1",
            insertbackground=TEXT_WHITE,
            font=("Consolas", 9),
            wrap=tk.WORD,
            relief=tk.FLAT,
            padx=10,
            pady=8
        )
        scrollbar = ttk.Scrollbar(console_frame, orient=tk.VERTICAL, command=self.log_text.yview)
        self.log_text.configure(yscrollcommand=scrollbar.set)

        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        self.log_text.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)

        # Text color tags
        self.log_text.tag_configure("INFO", foreground="#57f287")
        self.log_text.tag_configure("WARNING", foreground="#fee75c")
        self.log_text.tag_configure("ERROR", foreground="#ed4245")
        self.log_text.tag_configure("TIMESTAMP", foreground="#949ba4")
        self.log_text.tag_configure("DIM", foreground="#6d6f78")

    def _build_footer(self):
        footer_frame = tk.Frame(self.root, bg=BG_DARK, pady=6, padx=20)
        footer_frame.pack(fill=tk.X, side=tk.BOTTOM)

        tk.Label(
            footer_frame,
            text="Bot 101 v2.0 • 1-Click Host • YouTube, SoundCloud, Facebook, Telegram, Drive",
            font=("Segoe UI", 8),
            fg="#6d6f78",
            bg=BG_DARK
        ).pack(side=tk.LEFT)

    def _start_bot_action(self):
        if not self.controller.is_running:
            self.start_btn.configure(state=tk.DISABLED, bg=PANEL_BG, fg=TEXT_MUTED)
            self.disconnect_btn.configure(state=tk.NORMAL, bg=DISCORD_RED, fg=TEXT_WHITE)
            self._set_pill_status("CONNECTING", "#fee75c")
            self.tag_label.configure(text="Connecting to gateway...")
            self.controller.start()

    def _disconnect_bot_action(self):
        if self.controller.is_running:
            self.disconnect_btn.configure(state=tk.DISABLED, bg=PANEL_BG, fg=TEXT_MUTED)
            self.start_btn.configure(state=tk.NORMAL, bg=DISCORD_GREEN, fg=TEXT_WHITE)
            self._set_pill_status("DISCONNECTED", "#da373c")
            self.tag_label.configure(text="Offline (Disconnected)")
            self.guilds_label.configure(text="-")
            self.ping_label.configure(text="-")
            self.controller.disconnect()

    def _set_pill_status(self, text: str, color: str):
        self.status_dot.itemconfig(self.dot_item, fill=color)
        self.status_text_lbl.configure(text=text, fg=color)

    def _on_bot_status_changed(self, status: str, details: dict):
        def _apply():
            if status == "ONLINE":
                self._set_pill_status("ONLINE", DISCORD_GREEN)
                name = details.get("name", "Bot 101")
                guilds = details.get("guilds", 0)
                ping = details.get("ping", 0)
                self.tag_label.configure(text=name)
                self.guilds_label.configure(text=f"{guilds} Servers")
                self.ping_label.configure(text=f"{ping} ms")
                self.start_btn.configure(state=tk.DISABLED, bg=PANEL_BG, fg=TEXT_MUTED)
                self.disconnect_btn.configure(state=tk.NORMAL, bg=DISCORD_RED, fg=TEXT_WHITE)
            elif status == "OFFLINE":
                self._set_pill_status("OFFLINE", "#80848e")
                err = details.get("error")
                self.tag_label.configure(text=f"Offline ({err})" if err else "Offline")
                self.start_btn.configure(state=tk.NORMAL, bg=DISCORD_GREEN, fg=TEXT_WHITE)
                self.disconnect_btn.configure(state=tk.DISABLED, bg=PANEL_BG, fg=TEXT_MUTED)
            elif status == "CONNECTING":
                self._set_pill_status("CONNECTING", "#fee75c")
            elif status == "DISCONNECTING":
                self._set_pill_status("STOPPING", "#fee75c")

        self.root.after(0, _apply)

    def _periodic_stats_update(self):
        if self.controller.is_connected and self.controller.bot:
            try:
                ping = round(self.controller.bot.latency * 1000, 1) if self.controller.bot.latency else 0
                guilds = len(self.controller.bot.guilds)
                self.ping_label.configure(text=f"{ping} ms")
                self.guilds_label.configure(text=f"{guilds} Servers")
            except Exception:
                pass
        self.root.after(3000, self._periodic_stats_update)

    def _process_log_queue(self):
        while not self.log_queue.empty():
            try:
                msg, level = self.log_queue.get_nowait()
                self._append_log_line(msg, level)
            except queue.Empty:
                break
        self.root.after(80, self._process_log_queue)

    def _append_log_line(self, line: str, level: str):
        # Auto truncate if too many lines (keep max 1000 lines for RAM conservation)
        line_count = int(self.log_text.index("end-1c").split(".")[0])
        if line_count > 1000:
            self.log_text.delete("1.0", "150.0")

        # Color-coded insert
        self.log_text.insert(tk.END, f"{line}\n", level)

        if self.auto_scroll_var.get():
            self.log_text.see(tk.END)

    def _clear_logs(self):
        self.log_text.delete("1.0", tk.END)

    def _on_close(self):
        self.controller.disconnect()
        self.root.destroy()
        sys.exit(0)

def main():
    root = tk.Tk()
    app = Bot101GUI(root)
    root.mainloop()

if __name__ == "__main__":
    main()
