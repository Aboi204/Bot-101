---
name: structured-diagnostic-logger
description: >-
  Implements end-to-end Trace-ID correlation, rotating activity logs, structured JSON error tracebacks,
  and asynchronous FFmpeg stderr capture. Use across all bot modules, extractors, and voice callbacks.
---

# Structured Diagnostic Logger

Robust diagnostic logging ensures that silent playback failures, rate-limiting walls, and FFmpeg pipeline crashes are instantly traceable.

---

## 1. Trace-ID Correlation Architecture

Every slash command, user query, and background playback task generates a unique session trace ID:
`TRC-<HEX6>` (e.g. `TRC-A3F98B`).

This Trace-ID is propagated through:
1. User interaction handling
2. Audio stream URL resolution
3. Temporary audio file caching (`cache/audio/<trace_id>.ogg`)
4. FFmpeg process execution & stderr monitoring
5. Playback lifecycle events

---

## 2. File Targets & Schemas

### A. Activity Log (`logs/bot_activity.log`)
Rotated log file (max 10MB, 5 backups) with human-readable timestamped entries:
```text
2026-10-18 10:15:23 [INFO] [TRC-A3F98B] [Guild: 123456789] Slash command /play invoked with query: https://youtu.be/...
2026-10-18 10:15:24 [INFO] [TRC-A3F98B] Resolved YouTube stream in 320ms: title='Never Gonna Give You Up'
```

### B. Error Traces JSON (`logs/error_traces.json`)
JSON Lines format recording full diagnostic context for every failure:
```json
{
  "timestamp": "2026-10-18T10:15:25.123Z",
  "trace_id": "TRC-A3F98B",
  "guild_id": 123456789,
  "source_platform": "youtube",
  "input_url": "https://youtu.be/...",
  "file": "unified_resolver.py",
  "function": "resolve_youtube",
  "line_number": 84,
  "exception_type": "ExtractorError",
  "stack_trace": "Traceback (most recent call last):\n...",
  "ffmpeg_stderr": "HTTP error 403 Forbidden\nFailed to open segment..."
}
```

---

## 3. Core Implementation Requirements

1. **`@trace_and_log` Decorator**:
   Wraps functions and coroutines to measure execution time, inject `trace_id`, and catch exceptions to append to `logs/error_traces.json`.
2. **Async FFmpeg Stderr Reader**:
   Reads `stderr` line-by-line asynchronously to capture exact stream errors if FFmpeg terminates with non-zero exit codes.
3. **`/debug_logs` Slash Command**:
   Allows administrators to inspect the latest error traces directly within Discord.
