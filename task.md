# Autonomous Discord Music Bot Project Task Tracker

## Progress Overview
- [ ] Phase 0: Initialize Task & 6 Antigravity Skills (.agents/skills/)
  - [ ] chrome-cookie-auth-manager (SKILL.md & scripts/export_cookies.py)
  - [ ] multi-source-audio-resolver (SKILL.md & routing protocol)
  - [ ] structured-diagnostic-logger (SKILL.md & schema specs)
  - [ ] discord-portal-oauth-automator (SKILL.md)
  - [ ] voice-watchdog-self-healer (SKILL.md)
  - [ ] zero-cost-cloud-deployer (SKILL.md)
- [ ] Phase 1: Build Diagnostic Logger & Self-Healing Core
  - [ ] Directory structure (src/, src/extractors/, src/cogs/, src/utils/, cookies/, cache/audio/, logs/, tests/)
  - [ ] src/utils/logger.py with trace_id correlation, async FFmpeg stderr reader, @trace_and_log decorator
- [ ] Phase 2: Extract Chrome Cookies & Test All 5 Sources
  - [ ] Export cookies to cookies/cookies.txt via export_cookies.py
  - [ ] Implement src/extractors/unified_resolver.py (YouTube, SoundCloud, Facebook, Telegram, Google Drive)
  - [ ] Create & execute tests/verify_all_sources.py with headless 5s FFmpeg decode tests
  - [ ] Autonomously diagnose & self-heal any source failures until all 5 pass
- [ ] Phase 3: Build Discord Music Bot & Voice Watchdog
  - [ ] src/utils/voice_manager.py with dynamic -ss resume & automatic cache cleanup
  - [ ] src/cogs/music.py with all slash commands (/play, /pause, /resume, /skip, /stop, /queue, /nowplaying, /volume, /loop, /health, /debug_logs)
  - [ ] Bot lifecycle and idle timeout (5 minutes)
- [ ] Phase 4: Discord Portal Setup & Live Local Test
  - [ ] Discord Developer Portal automation / token retrieval & intents configuration
  - [ ] Local bot startup & slash command sync verification
- [ ] Phase 5: 100% Free Cloud Deployment & 24/7 Keep-Alive
  - [ ] Dockerfile, .dockerignore, requirements.txt
  - [ ] src/utils/keep_alive.py with /health and /logs endpoints
  - [ ] Cloud deployment (Wispbyte / Koyeb / Docker) & UptimeRobot monitor setup
