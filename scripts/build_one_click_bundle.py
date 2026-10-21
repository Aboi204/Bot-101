import os
import zipfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_ZIP = BASE_DIR / "Discord_Music_Bot_OneClick.zip"

INCLUDE_FILES = [
    "START_BOT.bat",
    "README_INSTRUCTIONS.txt",
    "requirements.txt",
    ".env",
    "bot.py",
    "main.py",
    "cookies/cookies.txt",
]

INCLUDE_DIRS = [
    "src",
]

def build_bundle():
    print(f"[*] Building 1-Click Portable Package: {OUTPUT_ZIP.name}...")
    if OUTPUT_ZIP.exists():
        OUTPUT_ZIP.unlink()

    with zipfile.ZipFile(OUTPUT_ZIP, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for rel_file in INCLUDE_FILES:
            file_path = BASE_DIR / rel_file
            if file_path.exists():
                arcname = f"Discord_Music_Bot/{rel_file}"
                zip_file.write(file_path, arcname=arcname)
                print(f"  + Added file: {arcname}")
            else:
                print(f"  [!] Missing file: {rel_file}")

        for rel_dir in INCLUDE_DIRS:
            dir_path = BASE_DIR / rel_dir
            for root, dirs, files in os.walk(dir_path):
                dirs[:] = [d for d in dirs if d not in ("__pycache__", ".git", ".pytest_cache")]
                for file in files:
                    if file.endswith((".pyc", ".log", ".tmp")):
                        continue
                    full_p = Path(root) / file
                    rel_p = full_p.relative_to(BASE_DIR)
                    arcname = f"Discord_Music_Bot/{rel_p.as_posix()}"
                    zip_file.write(full_p, arcname=arcname)
                    print(f"  + Added: {arcname}")

    size_kb = OUTPUT_ZIP.stat().st_size / 1024
    print(f"\n[SUCCESS] Package generated successfully: {OUTPUT_ZIP}")
    print(f"Size: {size_kb:.1f} KB")

if __name__ == "__main__":
    build_bundle()
