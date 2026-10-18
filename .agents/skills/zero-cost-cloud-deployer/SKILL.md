---
name: zero-cost-cloud-deployer
description: >-
  Packages the Discord bot into a lightweight Docker container and deploys it to 100% free
  hosting providers supporting outbound Voice UDP and FFmpeg, paired with an aiohttp health
  server and UptimeRobot keep-alive monitoring. Use during cloud deployment.
---

# Zero-Cost Cloud Deployer

Running a 24/7 Discord music bot at zero cost requires selecting providers that permit outbound UDP voice packets, providing sufficient RAM for FFmpeg transcoding, and preventing free-tier sleep cycles.

---

## 1. Free Platform Targets

1. **Wispbyte (Free Discord Bot Hosting)**:
   - Dedicated Discord bot hosting with native Python 3.11/3.12 and FFmpeg pre-installed.
   - Unrestricted UDP voice sockets.
2. **Koyeb (Free Tier)**:
   - 512MB RAM container instance.
   - Supports Dockerfile deployments and HTTP health checks.
3. **Self-Hosted / VPS Free Tiers**:
   - Oracle Cloud Always Free (2 AMD VMs or 4 ARM cores + 24GB RAM).
   - Fly.io (shared-cpu-1x with WireGuard/UDP).

---

## 2. Keep-Alive Architecture (`aiohttp`)

Free container providers often sleep instances after 15 minutes of inactivity if no HTTP traffic arrives. The bot incorporates an async web server on `0.0.0.0:8000`:

- `GET /health`: Returns `200 OK` JSON with uptime, memory, gateway ping, and voice connections.
- `GET /logs?token=<DEBUG_TOKEN>`: Returns the last 20 sanitized entries from `logs/error_traces.json`.

---

## 3. UptimeRobot Monitoring Setup

To ensure 24/7 continuous operation without sleep:
1. Access [UptimeRobot](https://uptimerobot.com/).
2. Add New Monitor:
   - **Monitor Type**: `HTTP(s)`
   - **Friendly Name**: `Discord Music Bot Health`
   - **URL / IP**: `https://<deployed-app-url>/health`
   - **Monitoring Interval**: Every 5 minutes.
3. The recurring requests prevent container idling.

---

## 4. Container Optimization

- Base image: `python:3.11-slim`
- Required packages: `ffmpeg`, `libopus0`, `libsodium23`, `git`
- Environment variables: Inject `DISCORD_TOKEN`, `COOKIES_B64` (base64 decoded at container start into `cookies/cookies.txt`).
