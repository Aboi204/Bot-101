import time
import subprocess
import yt_dlp
import re
from pathlib import Path

# Clean URL helper
def clean_youtube_url(url: str) -> str:
    # If it has a video ID (watch?v=XXXX or youtu.be/XXXX), isolate the video ID
    v_match = re.search(r'(?:v=|/shorts/|youtu\.be/)([a-zA-Z0-9_-]{11})', url)
    if v_match:
        video_id = v_match.group(1)
        return f"https://www.youtube.com/watch?v={video_id}"
    return url

test_url = "https://www.youtube.com/watch?v=vU1-yqG9DEU&list=RDvU1-yqG9DEU&start_radio=1"
cleaned = clean_youtube_url(test_url)
print(f"Original: {test_url}")
print(f"Cleaned:  {cleaned}")

t0 = time.time()
ydl_opts = {
    'format': 'bestaudio/best',
    'noplaylist': True,
    'quiet': True,
    'no_warnings': True,
    'source_address': '0.0.0.0',
    'nocheckcertificate': True,
}

with yt_dlp.YoutubeDL(ydl_opts) as ydl:
    info = ydl.extract_info(cleaned, download=False)

elapsed = time.time() - t0
print(f"[OK] Extracted '{info.get('title')}' in {elapsed:.2f}s!")
stream_url = info.get('url')
print(f"Stream URL exists: {bool(stream_url)}")

# Test FFmpeg direct stream decoding
ffmpeg = r"C:\Users\ISLAM\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.2-full_build\bin\ffmpeg.exe"
cmd = [
    ffmpeg,
    "-reconnect", "1",
    "-reconnect_streamed", "1",
    "-reconnect_delay_max", "5",
    "-nostdin",
    "-i", stream_url,
    "-t", "5",
    "-f", "null",
    "-"
]

t1 = time.time()
res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
decode_elapsed = time.time() - t1
print(f"[OK] FFmpeg decoded 5 seconds in {decode_elapsed:.2f}s with return code {res.returncode}")
if res.returncode != 0:
    print("Stderr:", res.stderr[-500:])
