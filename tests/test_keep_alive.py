import asyncio
import os
import sys
import aiohttp
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from src.utils.keep_alive import KeepAliveServer

async def test_server():
    server = KeepAliveServer(port=8089)
    await server.start()

    async with aiohttp.ClientSession() as session:
        # Test /health
        async with session.get("http://127.0.0.1:8089/health") as resp:
            assert resp.status == 200, f"Health endpoint returned {resp.status}"
            data = await resp.json()
            assert data["status"] == "healthy", "Expected status healthy"
            print("[PASS] Keep-Alive /health endpoint verified:", data)

        # Test /logs with valid token
        async with session.get("http://127.0.0.1:8089/logs?token=free_music_bot_secret_token") as resp:
            assert resp.status == 200, f"Logs endpoint returned {resp.status}"
            logs_data = await resp.json()
            print(f"[PASS] Keep-Alive /logs endpoint verified (count={logs_data['count']})")

        # Test /logs with invalid token (expect 401)
        async with session.get("http://127.0.0.1:8089/logs?token=invalid") as resp:
            assert resp.status == 401, f"Expected 401 for bad token, got {resp.status}"
            print("[PASS] Keep-Alive /logs 401 unauthorized security check passed.")

    await server.stop()
    print("[PASS] Keep-Alive server tests finished successfully.")

if __name__ == "__main__":
    asyncio.run(test_server())
