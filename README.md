# Bot 101 🎵

A high-performance, feature-packed Discord Music Bot supporting multi-platform streaming, dynamic audio normalization, rich interactive UI buttons, and standalone GUI executable packaging.

---

## ✨ Features

- **Multi-Source Audio Resolver**: Seamless streaming from:
  - **YouTube** (Videos, Playlists, Shorts)
  - **SoundCloud** (Tracks & Playlists)
  - **Facebook Watch** (Public & private video streams)
  - **Telegram** (Direct channel audio / video voice messages)
  - **Direct URLs** & HTTP live streams
- **Smart Voice Channel Management**:
  - Requires users to be inside a voice channel before requesting playback.
  - Automatically disconnects and frees server resources when the channel is empty.
- **Interactive UI Dashboard**:
  - Live track controls: ⏯️ Pause/Resume, ⏭️ Skip, ⏹️ Stop, 📜 Queue, 🔀 Shuffle, 🔁 Loop, 🔊 Volume Boost.
  - Ephemeral user feedback with dynamic player sync.
- **Enhanced Audio Pipeline**:
  - Dynamic volume boost (`+6.9dB`) paired with brickwall peak limiter in FFmpeg to eliminate distortion and low-volume tracks.
- **Minimalist Dark Desktop GUI**:
  - Single-click start & disconnect controls.
  - Real-time logging console without annoying black CMD windows.
- **Cloud & Docker Ready**:
  - Includes `Dockerfile` and `docker-compose.yml` with built-in keep-alive HTTP server for zero-cost cloud hosting.

---

## 🚀 Quick Start

### 1. Prerequisites
- **Python 3.10+**
- **FFmpeg** installed and added to your system `PATH`.

### 2. Installation
Clone the repository:
```bash
git clone https://github.com/Aboi204/Bot-101.git
cd Bot-101
```

Create a virtual environment and install dependencies:
```bash
python -m venv venv
# Windows:
venv\Scripts\activate
# Linux/macOS:
source venv/bin/activate

pip install -r requirements.txt
```

### 3. Configuration
Copy the example environment file and insert your Discord Bot Token:
```bash
cp .env.example .env
```
Edit `.env`:
```env
DISCORD_TOKEN=your_token_here
BOT_PREFIX=/
```

### 4. Running the Bot

#### Option A: Minimalist GUI (Desktop)
```bash
python bot.py
```

#### Option B: CLI Mode (Headless / Server)
```bash
python bot.py --cli
```

#### Option C: Docker
```bash
docker compose up -d --build
```

---

## 🛠️ Building the Standalone Executable

To package the bot into a standalone Windows `.exe` (`Bot 101.exe`) with the custom icon and embedded GUI:

```bash
python scripts/build_exe.py
```
The output file will be generated in the root directory as `Bot 101.exe`.

---

## 📋 Slash Commands

| Command | Description |
| :--- | :--- |
| `/play <query/url>` | Play audio from YouTube, SoundCloud, Facebook, Telegram, etc. |
| `/pause` | Pause current track |
| `/resume` | Resume playback |
| `/skip` | Skip to the next track in queue |
| `/stop` | Clear queue and stop playback |
| `/queue` | Display currently queued tracks |
| `/nowplaying` | Display details and interactive UI for the current song |
| `/volume <1-200>` | Adjust playback volume level |
| `/shuffle` | Randomize the upcoming queue |
| `/loop` | Toggle repeat mode (Track / Queue / Off) |

---

## 🛡️ License
Distributed under the MIT License.
