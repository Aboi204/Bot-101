# Discord Music Bot & Agent Skills

An enterprise-grade, high-reliability Discord Music Bot with multi-source audio resolving (YouTube, SoundCloud, Spotify), Chrome cookie authentication against bot detection/403 errors, structured diagnostic telemetry, and zero-cost cloud deployment playbooks.

---

## 📁 Project Architecture & Agent Skills

```text
discord-music-bot/
├── .agents/
│   └── skills/
│       ├── chrome-cookie-auth-manager/
│       │   ├── SKILL.md
│       │   └── scripts/
│       │       └── export_cookies.py
│       ├── multi-source-audio-resolver/
│       │   ├── SKILL.md
│       │   └── scripts/
│       │       └── test_extractors.py
│       ├── structured-diagnostic-logger/
│       │   └── SKILL.md
│       └── zero-cost-cloud-deployer/
│           └── SKILL.md
├── audio/
│   ├── player.py          # Guild player, queue, voice state & FFmpeg reconnect streaming
│   └── resolver.py        # yt-dlp multi-source stream & Spotify metadata resolver
├── cogs/
│   └── music.py           # Discord slash commands (/play, /queue, /diagnostics, etc.)
├── utils/
│   └── logger.py          # Structured JSON & colored console diagnostic logger
├── bot.py                 # Bot lifecycle & command sync entry point
├── config.py              # Environment configuration loader
├── requirements.txt       # Python dependencies
├── .env.example           # Environment template
├── Dockerfile             # Container configuration with FFmpeg & Opus
└── docker-compose.yml     # Docker Compose deployment setup
```

---

## ⚡ Quick Start

### 1. Prerequisites
- Python 3.10+
- [FFmpeg](https://ffmpeg.org/download.html) installed and accessible in your system `PATH`.

### 2. Installation
```bash
cd discord-music-bot
python -m venv venv
# On Windows:
venv\Scripts\activate
# On Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Configuration
Copy `.env.example` to `.env` and enter your Discord bot token:
```bash
cp .env.example .env
```
Edit `.env`:
```ini
DISCORD_TOKEN=your_token_here
BOT_PREFIX=!
COOKIE_FILE=cookies.txt
```

### 4. Running the Bot
```bash
python bot.py
```

---

## 🎵 Slash Commands

| Command | Description |
| :--- | :--- |
| `/play <query>` | Play a track/playlist from YouTube, SoundCloud, or Spotify URL/search. |
| `/pause` | Pause current playback. |
| `/resume` | Resume playback. |
| `/skip` | Skip the current track. |
| `/stop` | Stop playback and clear the queue. |
| `/nowplaying` | Show currently playing song with visual progress bar. |
| `/queue` | Display upcoming tracks. |
| `/volume <1-150>` | Adjust playback volume. |
| `/loop <off\|track\|queue>` | Set repeat mode. |
| `/leave` | Disconnect the bot from the voice channel. |
| `/diagnostics` | View real-time bot telemetry (RAM, CPU, Voice Ping, Cookie Auth). |

---

## 🛠️ Specialized Agent Skills

The `.agents/skills/` directory contains specialized operational skills and scripts:

1. **`chrome-cookie-auth-manager`**:
   - Runbook to prevent YouTube bot detection, CAPTCHAs, and 403 errors.
   - Script: `.agents/skills/chrome-cookie-auth-manager/scripts/export_cookies.py` decrypts cookies from Chrome/Edge/Brave into `cookies.txt`.
2. **`multi-source-audio-resolver`**:
   - Architectural specs for stream extraction across YouTube, SoundCloud, and Spotify.
   - Script: `.agents/skills/multi-source-audio-resolver/scripts/test_extractors.py` tests extraction pipeline and connectivity.
3. **`structured-diagnostic-logger`**:
   - Standards for JSON log events (`playback_start`, `voice_disconnect`, `ffmpeg_error`) and telemetry monitoring.
4. **`zero-cost-cloud-deployer`**:
   - Production guides for running the bot 24/7 on free/low-cost platforms (Oracle Cloud Always Free, Fly.io, Render, Koyeb).
