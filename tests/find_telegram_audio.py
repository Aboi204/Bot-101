import urllib.request
import re

candidates = [
    "https://t.me/classical_music/5",
    "https://t.me/classical_music/8",
    "https://t.me/piano/5",
    "https://t.me/c/test",
    "https://t.me/audiotests/2",
    "https://t.me/audiotests/3",
    "https://t.me/music_box/10",
    "https://t.me/nocopyrightsounds/5",
    "https://t.me/telegram/189",
    "https://t.me/durov/150",
    "https://t.me/durov/175"
]

print("Scanning candidate Telegram messages...")
for url in candidates:
    try:
        embed_url = f"{url}?embed=1"
        req = urllib.request.Request(embed_url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
            audios = re.findall(r'<audio[^>]+src=["\']([^"\']+)["\']', html)
            videos = re.findall(r'<video[^>]+src=["\']([^"\']+)["\']', html)
            if audios or videos:
                print(f"FOUND MEDIA at {url}: audios={audios}, videos={videos}")
    except Exception as e:
        pass
