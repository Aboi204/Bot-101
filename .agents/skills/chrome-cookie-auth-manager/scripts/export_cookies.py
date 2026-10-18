#!/usr/bin/env python3
"""
Chrome Cookie Auth Manager Exporter
Extracts, unlocks, decrypts, and validates cookies from ALL Google Chrome profiles for YouTube, Facebook, SoundCloud, and Google Drive.
"""

import argparse
import base64
import json
import os
import platform
import shutil
import sqlite3
import subprocess
import sys
import tempfile
from datetime import datetime, timedelta

TARGET_DOMAINS = [
    "youtube.com",
    "google.com",
    "facebook.com",
    "soundcloud.com",
    "drive.google.com"
]

def get_dpapi_secret(encrypted_key: bytes) -> bytes:
    try:
        import win32crypt
        return win32crypt.CryptUnprotectData(encrypted_key, None, None, None, 0)[1]
    except ImportError:
        import ctypes
        from ctypes import wintypes

        class DATA_BLOB(ctypes.Structure):
            _fields_ = [
                ("cbData", wintypes.DWORD),
                ("pbData", ctypes.POINTER(ctypes.c_byte))
            ]

        pDataIn = DATA_BLOB()
        pDataIn.cbData = len(encrypted_key)
        pDataIn.pbData = (ctypes.c_byte * len(encrypted_key)).from_buffer_copy(encrypted_key)

        pDataOut = DATA_BLOB()
        crypt32 = ctypes.windll.crypt32

        if not crypt32.CryptUnprotectData(
            ctypes.byref(pDataIn), None, None, None, None, 0, ctypes.byref(pDataOut)
        ):
            raise RuntimeError("CryptUnprotectData failed.")

        raw_key = ctypes.string_at(pDataOut.pbData, pDataOut.cbData)
        ctypes.windll.kernel32.LocalFree(pDataOut.pbData)
        return raw_key

def get_master_key(local_state_path: str) -> bytes:
    with open(local_state_path, "r", encoding="utf-8") as f:
        local_state = json.load(f)
    encrypted_key = base64.b64decode(local_state["os_crypt"]["encrypted_key"])
    return get_dpapi_secret(encrypted_key[5:])

def decrypt_value(encrypted_value: bytes, master_key: bytes) -> str:
    if not encrypted_value:
        return ""
    if encrypted_value.startswith(b"v10") or encrypted_value.startswith(b"v11"):
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            nonce = encrypted_value[3:15]
            ciphertext = encrypted_value[15:-16]
            tag = encrypted_value[-16:]
            aesgcm = AESGCM(master_key)
            return aesgcm.decrypt(nonce, ciphertext + tag, None).decode("utf-8", errors="replace")
        except Exception:
            return ""
    try:
        return get_dpapi_secret(encrypted_value).decode("utf-8", errors="replace")
    except Exception:
        return ""

def locate_chrome_profiles():
    os_name = platform.system()
    if os_name == "Windows":
        local_app = os.environ.get("LOCALAPPDATA", "")
        user_data = os.path.join(local_app, "Google", "Chrome", "User Data")
    elif os_name == "Darwin":
        user_data = os.path.expanduser("~/Library/Application Support/Google/Chrome")
    else:
        user_data = os.path.expanduser("~/.config/google-chrome")

    local_state = os.path.join(user_data, "Local State") if user_data else None

    cookie_dbs = []
    if os.path.exists(user_data):
        for entry in os.listdir(user_data):
            profile_dir = os.path.join(user_data, entry)
            if os.path.isdir(profile_dir):
                for candidate in [os.path.join(profile_dir, "Network", "Cookies"), os.path.join(profile_dir, "Cookies")]:
                    if os.path.exists(candidate):
                        cookie_dbs.append((entry, candidate))

    return user_data, local_state, cookie_dbs

def export_all_profile_cookies(output_file: str) -> bool:
    user_data, local_state, cookie_dbs = locate_chrome_profiles()
    if not local_state or not os.path.exists(local_state):
        print(f"[!] Chrome Local State not found: {local_state}")
        return False

    try:
        master_key = get_master_key(local_state)
    except Exception as e:
        print(f"[!] Could not decrypt Chrome master key: {e}")
        return False

    print(f"[*] Found {len(cookie_dbs)} Chrome profile cookie databases.")
    all_cookies = {}  # (domain, path, name) -> (is_secure, expires, value)

    for profile_name, db_path in cookie_dbs:
        temp_dir = tempfile.mkdtemp()
        temp_db = os.path.join(temp_dir, "Cookies.tmp")
        try:
            shutil.copy2(db_path, temp_db)
            conn = sqlite3.connect(temp_db)
            cursor = conn.cursor()
            cursor.execute("SELECT host_key, path, is_secure, expires_utc, name, encrypted_value FROM cookies")
            rows = cursor.fetchall()
            conn.close()

            profile_hits = 0
            for host_key, path, is_secure, expires_utc, name, encrypted_value in rows:
                if not any(domain in host_key for domain in TARGET_DOMAINS):
                    continue
                val = decrypt_value(encrypted_value, master_key)
                if not val:
                    continue

                if expires_utc > 0:
                    unix_expires = int((expires_utc / 1000000) - 11644473600)
                else:
                    unix_expires = int((datetime.now() + timedelta(days=365)).timestamp())

                all_cookies[(host_key, path, name)] = (is_secure, unix_expires, val)
                profile_hits += 1

            print(f"[*] Profile '{profile_name}': Extracted {profile_hits} target cookies.")
        except Exception as e:
            print(f"[!] Could not read profile '{profile_name}': {e}")
        finally:
            shutil.rmtree(temp_dir, ignore_errors=True)

    netscape_lines = [
        "# Netscape HTTP Cookie File",
        "# Exported by chrome-cookie-auth-manager",
        f"# Generated: {datetime.now().isoformat()}",
        ""
    ]

    for (host_key, path, name), (is_secure, unix_expires, val) in all_cookies.items():
        is_subdomain = "TRUE" if host_key.startswith(".") else "FALSE"
        secure_flag = "TRUE" if is_secure else "FALSE"
        netscape_lines.append(f"{host_key}\t{is_subdomain}\t{path}\t{secure_flag}\t{unix_expires}\t{name}\t{val}")

    os.makedirs(os.path.dirname(os.path.abspath(output_file)), exist_ok=True)
    with open(output_file, "w", encoding="utf-8") as f:
        f.write("\n".join(netscape_lines) + "\n")

    print(f"[+] Total unique target cookies written to {output_file}: {len(all_cookies)}")
    return len(all_cookies) > 0

def main():
    parser = argparse.ArgumentParser(description="Export unlocked Chrome cookies across all profiles")
    parser.add_argument("--output", default="cookies/cookies.txt", help="Destination file path")
    args = parser.parse_args()

    out = os.path.abspath(args.output)
    success = export_all_profile_cookies(out)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()
