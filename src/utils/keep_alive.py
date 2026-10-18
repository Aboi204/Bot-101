import asyncio
import json
import os
import platform
import time
from pathlib import Path
from typing import Optional

from aiohttp import web
import psutil

from src.utils.logger import ERROR_TRACES_FILE, log

class KeepAliveServer:
    def __init__(self, bot=None, port: int = 8000):
        self.bot = bot
        self.port = port
        self.start_time = time.time()
        self.app = web.Application()
        self.app.router.add_get("/", self.handle_root)
        self.app.router.add_get("/health", self.handle_health)
        self.app.router.add_get("/logs", self.handle_logs)
        self.runner: Optional[web.AppRunner] = None

    async def handle_root(self, request: web.Request) -> web.Response:
        return web.Response(text="Discord Music Bot Keep-Alive Server is running 24/7.", status=200)

    async def handle_health(self, request: web.Request) -> web.Response:
        uptime_sec = int(time.time() - self.start_time)
        process = psutil.Process(os.getpid())
        mem_mb = round(process.memory_info().rss / (1024 * 1024), 2)
        cpu_pct = round(process.cpu_percent(interval=None), 1)

        voice_sessions = len(self.bot.voice_clients) if self.bot else 0
        gateway_ping = round(self.bot.latency * 1000, 1) if (self.bot and self.bot.latency) else None

        cookie_path = Path("cookies/cookies.txt")
        cookies_ok = cookie_path.exists() and cookie_path.stat().st_size > 100

        data = {
            "status": "healthy",
            "uptime_seconds": uptime_sec,
            "memory_rss_mb": mem_mb,
            "cpu_percent": cpu_pct,
            "active_voice_sessions": voice_sessions,
            "gateway_latency_ms": gateway_ping,
            "cookies_authenticated": cookies_ok,
            "python_version": platform.python_version(),
            "timestamp": time.time()
        }
        return web.json_response(data, status=200)

    async def handle_logs(self, request: web.Request) -> web.Response:
        token = request.query.get("token", "")
        expected_token = os.getenv("DEBUG_TOKEN", "free_music_bot_secret_token")

        if token != expected_token:
            return web.json_response({"error": "Unauthorized. Invalid token query parameter."}, status=401)

        traces = []
        if ERROR_TRACES_FILE.exists():
            with open(ERROR_TRACES_FILE, "r", encoding="utf-8") as f:
                for line in f:
                    if line.strip():
                        try:
                            traces.append(json.loads(line.strip()))
                        except Exception:
                            pass

        return web.json_response({
            "count": min(20, len(traces)),
            "recent_traces": traces[-20:]
        }, status=200)

    async def start(self):
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, "0.0.0.0", self.port)
        await site.start()
        log.info(f"Keep-Alive HTTP server listening on http://0.0.0.0:{self.port} (endpoints: /health, /logs)")

    async def stop(self):
        if self.runner:
            await self.runner.cleanup()

async def run_standalone():
    server = KeepAliveServer(port=int(os.getenv("PORT", 8000)))
    await server.start()
    while True:
        await asyncio.sleep(3600)

if __name__ == "__main__":
    asyncio.run(run_standalone())
