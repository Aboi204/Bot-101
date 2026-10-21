import os
import shutil
import subprocess
import sys
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent

if sys.stdout.encoding.lower() != "utf-8":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

def find_ffmpeg() -> Path:
    # 1. Winget directory
    local_app = os.environ.get("LOCALAPPDATA", "")
    if local_app:
        winget_pattern = Path(local_app) / "Microsoft" / "WinGet" / "Packages"
        if winget_pattern.exists():
            for p in winget_pattern.glob("*FFmpeg*/**/ffmpeg.exe"):
                if p.is_file():
                    return p.resolve()

    # 2. System PATH
    which_ffmpeg = shutil.which("ffmpeg")
    if which_ffmpeg:
        return Path(which_ffmpeg).resolve()

    # 3. Local dirs
    for candidate in [ROOT_DIR / "bin" / "ffmpeg.exe", ROOT_DIR / "ffmpeg.exe"]:
        if candidate.is_file():
            return candidate.resolve()

    raise FileNotFoundError("Could not find ffmpeg.exe to bundle!")

def build_standalone_exe():
    print("=" * 60)
    print("[*] BUILDING 1-CLICK STANDALONE EXECUTABLE (Discord_Music_Bot.exe)")
    print("=" * 60)

    ffmpeg_path = find_ffmpeg()
    print(f"[+] Found FFmpeg at: {ffmpeg_path} ({round(os.path.getsize(ffmpeg_path)/(1024*1024), 1)} MB)")

    env_path = ROOT_DIR / ".env"
    if not env_path.is_file():
        raise FileNotFoundError(".env file not found!")
    print(f"[+] Found .env config at: {env_path}")

    cookies_path = ROOT_DIR / "cookies" / "cookies.txt"
    if not cookies_path.is_file():
        raise FileNotFoundError("cookies/cookies.txt not found!")
    print(f"[+] Found cookies at: {cookies_path}")

    import discord
    opus_dll = Path(discord.__file__).parent / "bin" / "libopus-0.x64.dll"
    if not opus_dll.is_file():
        raise FileNotFoundError(f"libopus dll not found at {opus_dll}")
    print(f"[+] Found Discord Opus DLL at: {opus_dll} ({round(os.path.getsize(opus_dll)/1024, 1)} KB)")

    icon_path = ROOT_DIR / "assets" / "bot_icon.ico"
    if not icon_path.is_file():
        from scripts.generate_icon import create_discord_green_icon
        create_discord_green_icon()
    print(f"[+] Found custom icon at: {icon_path}")

    # Build PyInstaller command
    cmd = [
        sys.executable,
        "-m", "PyInstaller",
        "--noconfirm",
        "--clean",
        "--onefile",
        "--noconsole",
        "--name", "Bot 101",
        "--icon", str(icon_path),
        # Data bundles
        "--add-data", f"{env_path};.",
        "--add-data", f"{ROOT_DIR / 'cookies'};cookies",
        "--add-data", f"{ROOT_DIR / 'src'};src",
        "--add-data", f"{ROOT_DIR / 'assets'};assets",
        # Voice binaries (Opus audio encoder for Discord voice channels)
        "--add-binary", f"{opus_dll};.",
        "--add-binary", f"{opus_dll};discord/bin",
        # Exclude heavy unused packages to keep file size minimal
        "--exclude-module", "numpy",
        "--exclude-module", "matplotlib",
        "--exclude-module", "pandas",
        "--exclude-module", "scipy",
        "--exclude-module", "unittest",
        "--exclude-module", "pydoc",
        # Full package collections & C extensions
        "--collect-all", "nacl",
        "--collect-all", "discord",
        "--hidden-import", "nacl._sodium",
        "--hidden-import", "discord",
        "--hidden-import", "aiohttp",
        "--hidden-import", "yt_dlp",
        "--hidden-import", "psutil",
        # Hidden imports
        "--hidden-import", "src.gui",
        "--hidden-import", "src.cogs.music",
        "--hidden-import", "src.utils.voice_manager",
        "--hidden-import", "src.utils.ui_controls",
        "--hidden-import", "src.utils.logger",
        "--hidden-import", "src.utils.keep_alive",
        "--hidden-import", "src.extractors.unified_resolver",
        # Entry point
        str(ROOT_DIR / "bot.py"),
    ]

    print("[*] Running PyInstaller build... (this may take 1-2 minutes)")
    res = subprocess.run(cmd, cwd=str(ROOT_DIR))
    if res.returncode != 0:
        print("[!] PyInstaller build failed!")
        sys.exit(res.returncode)

    dist_exe = ROOT_DIR / "dist" / "Bot 101.exe"
    if not dist_exe.is_file():
        print(f"[!] Executable not found at {dist_exe}")
        sys.exit(1)

    # Also copy to root for super easy access
    root_exe = ROOT_DIR / "Bot 101.exe"
    shutil.copy2(dist_exe, root_exe)

    size_mb = round(os.path.getsize(root_exe) / (1024 * 1024), 2)
    print("=" * 60)
    print("[OK] BUILD SUCCESSFUL!")
    print(f"[+] Standalone 1-Click Executable: {root_exe}")
    print(f"[+] Total Single-File Size: {size_mb} MB")
    print("=" * 60)

if __name__ == "__main__":
    build_standalone_exe()
