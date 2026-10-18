---
name: chrome-cookie-auth-manager
description: >-
  Extracts, unlocks, and validates Netscape-format cookies from Google Chrome for YouTube, Facebook,
  SoundCloud, and Google Drive. Use whenever initializing authentication or recovering from HTTP 403/401,
  login walls, or bot-detection errors.
---

# Chrome Cookie Auth Manager

Modern media platforms (YouTube, Facebook, SoundCloud, Google Drive) impose strict bot-detection, rate limits, and login walls on datacenter IPs or unauthenticated automated requests.

This skill provides automated extraction, unlocking, decryption, and validation of Chrome browser cookies into standard Netscape `cookies/cookies.txt` format.

---

## 1. Capabilities & Workflow

1. **Autonomous Profile Discovery**: Automatically locates Google Chrome's User Data directory across Windows (`%LOCALAPPDATA%\Google\Chrome\User Data`), Linux, and macOS.
2. **Lock Bypass**: When Chrome is currently running, Windows locks the SQLite `Cookies` file. The tool automatically clones the active database and local state to a temporary workspace before querying.
3. **Multi-Domain Extraction**: Filters and decrypts session cookies across required targets:
   - YouTube: `.youtube.com`, `.google.com`
   - Facebook: `.facebook.com`, `.fb.watch`
   - SoundCloud: `.soundcloud.com`
   - Google Drive: `drive.google.com`, `accounts.google.com`
4. **Validation**: Executes headless probe tests to verify that extracted cookies successfully authenticate against YouTube and Facebook without HTTP 403/401 responses.

---

## 2. Running Cookie Export

Run the bundled Python helper:

```bash
python .agents/skills/chrome-cookie-auth-manager/scripts/export_cookies.py --output cookies/cookies.txt
```

Options:
- `--browser [chrome|edge|brave]` (Default: `chrome`)
- `--output <path>` (Default: `cookies/cookies.txt`)
- `--verify` (Runs verification against YouTube and Facebook endpoints)

Refer to: [export_cookies.py](./scripts/export_cookies.py)

---

## 3. Bot Integration

The audio extractors and `yt-dlp` instances read `cookies/cookies.txt` automatically:
```python
import os

COOKIE_FILE = os.getenv("COOKIE_FILE", "cookies/cookies.txt")
ydl_opts = {
    'cookiefile': COOKIE_FILE if os.path.exists(COOKIE_FILE) else None,
    'format': 'bestaudio/best',
}
```
