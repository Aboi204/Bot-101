import base64
import os
import zipfile
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
OUTPUT_ZIP = BASE_DIR / "deploy_package.zip"
COOKIES_FILE = BASE_DIR / "cookies" / "cookies.txt"

def build_package():
    print("[+] Building cloud deployment package...")
    
    # 1. Base64 encode cookies
    cookies_b64 = ""
    if COOKIES_FILE.exists():
        with open(COOKIES_FILE, "rb") as f:
            cookies_b64 = base64.b64encode(f.read()).decode("utf-8")
        print(f"    [OK] Encoded cookies/cookies.txt ({len(cookies_b64)} chars)")
    else:
        print("    [!] Warning: cookies/cookies.txt not found.")

    # 2. Files and folders to include
    include_paths = [
        ("src", BASE_DIR / "src"),
        ("cookies", BASE_DIR / "cookies"),
        ("requirements.txt", BASE_DIR / "requirements.txt"),
        ("bot.py", BASE_DIR / "bot.py"),
        ("main.py", BASE_DIR / "main.py"),
        ("Dockerfile", BASE_DIR / "Dockerfile"),
        (".env", BASE_DIR / ".env"),
    ]

    # Create zip file
    if OUTPUT_ZIP.exists():
        OUTPUT_ZIP.unlink()

    with zipfile.ZipFile(OUTPUT_ZIP, "w", zipfile.ZIP_DEFLATED) as zipf:
        for archive_name, path in include_paths:
            if not path.exists():
                continue
            if path.is_file():
                zipf.write(path, archive_name)
                print(f"    + Added file: {archive_name}")
            elif path.is_dir():
                for root, dirs, files in os.walk(path):
                    # Skip __pycache__ and temp files
                    if "__pycache__" in root:
                        continue
                    for file in files:
                        if file.endswith((".pyc", ".tmp", ".log")):
                            continue
                        full_path = Path(root) / file
                        rel_path = full_path.relative_to(BASE_DIR)
                        zipf.write(full_path, str(rel_path))
                print(f"    + Added directory: {archive_name}")

    zip_size_kb = OUTPUT_ZIP.stat().st_size / 1024
    print(f"\n[SUCCESS] Package created successfully: {OUTPUT_ZIP.name} ({zip_size_kb:.1f} KB)")
    print(f"Location: {OUTPUT_ZIP.absolute()}\n")

    return cookies_b64

if __name__ == "__main__":
    b64 = build_package()
