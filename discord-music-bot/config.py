import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

# Load .env file from base directory
load_dotenv(dotenv_path=BASE_DIR / ".env")

DISCORD_TOKEN = os.getenv("DISCORD_TOKEN", "")
BOT_PREFIX = os.getenv("BOT_PREFIX", "!")

COOKIE_FILE = os.getenv("COOKIE_FILE", str(BASE_DIR / "cookies.txt"))
DEFAULT_VOLUME = float(os.getenv("DEFAULT_VOLUME", "0.5"))
MAX_QUEUE_SIZE = int(os.getenv("MAX_QUEUE_SIZE", "100"))
IDLE_TIMEOUT_SECONDS = int(os.getenv("IDLE_TIMEOUT_SECONDS", "300"))

SPOTIFY_CLIENT_ID = os.getenv("SPOTIFY_CLIENT_ID", "")
SPOTIFY_CLIENT_SECRET = os.getenv("SPOTIFY_CLIENT_SECRET", "")

LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO").upper()
LOG_FILE = os.getenv("LOG_FILE", str(BASE_DIR / "logs" / "bot.log"))
JSON_LOGS = os.getenv("JSON_LOGS", "true").lower() in ("true", "1", "yes")

# Ensure logs directory exists
os.makedirs(os.path.dirname(LOG_FILE), exist_ok=True)
