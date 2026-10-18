import os
import urllib.request
import json
from dotenv import load_dotenv

load_dotenv()
token = os.getenv("DISCORD_TOKEN")
headers = {
    "Authorization": f"Bot {token}",
    "User-Agent": "DiscordBot (https://github.com, 1.0)"
}

req = urllib.request.Request("https://discord.com/api/v10/users/@me/guilds", headers=headers)
with urllib.request.urlopen(req) as resp:
    guilds = json.loads(resp.read().decode("utf-8"))

for g in guilds:
    print(f"\nGuild: {g['name']} (ID: {g['id']})")
    c_req = urllib.request.Request(f"https://discord.com/api/v10/guilds/{g['id']}/channels", headers=headers)
    with urllib.request.urlopen(c_req) as c_resp:
        channels = json.loads(c_resp.read().decode("utf-8"))
        for c in channels:
            if c.get("type") == 0:  # Text channel
                print(f"  - #{c['name']} (ID: {c['id']})")
