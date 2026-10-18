import asyncio
import functools
import inspect
import json
import logging
import os
import secrets
import sys
import time
import traceback
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Callable, Dict, Optional

# Ensure directories exist
BASE_DIR = Path(__file__).resolve().parent.parent.parent
LOGS_DIR = BASE_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

ACTIVITY_LOG_FILE = LOGS_DIR / "bot_activity.log"
ERROR_TRACES_FILE = LOGS_DIR / "error_traces.json"

def generate_trace_id() -> str:
    """Generates a unique TRC-XXXXXX correlation ID."""
    return f"TRC-{secrets.token_hex(3).upper()}"

class BotActivityFormatter(logging.Formatter):
    """Formats human-readable logs for bot_activity.log and console."""
    COLORS = {
        logging.DEBUG: "\033[36m",
        logging.INFO: "\033[32m",
        logging.WARNING: "\033[33m",
        logging.ERROR: "\033[31m",
        logging.CRITICAL: "\033[41m",
    }
    RESET = "\033[0m"

    def __init__(self, use_color: bool = False):
        super().__init__()
        self.use_color = use_color

    def format(self, record: logging.LogRecord) -> str:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        trace_id = getattr(record, "trace_id", "TRC-SYSTEM")
        guild_id = getattr(record, "guild_id", None)
        guild_str = f" [Guild: {guild_id}]" if guild_id else ""
        level = record.levelname

        message = record.getMessage()
        if self.use_color:
            color = self.COLORS.get(record.levelno, self.RESET)
            formatted = f"{color}{timestamp} [{level:<7}] [{trace_id}]{guild_str} {message}{self.RESET}"
        else:
            formatted = f"{timestamp} [{level:<7}] [{trace_id}]{guild_str} {message}"

        if record.exc_info:
            formatted += "\n" + self.formatException(record.exc_info)
        return formatted

def setup_activity_logger(name: str = "discord_music_bot") -> logging.Logger:
    logger = logging.getLogger(name)
    logger.setLevel(logging.INFO)
    logger.handlers.clear()

    # Console output
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(BotActivityFormatter(use_color=True))
    logger.addHandler(console_handler)

    # Rotating activity file handler (10MB max, 5 backups)
    file_handler = RotatingFileHandler(
        str(ACTIVITY_LOG_FILE),
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8"
    )
    file_handler.setFormatter(BotActivityFormatter(use_color=False))
    logger.addHandler(file_handler)

    return logger

log = setup_activity_logger()

def record_error_trace(
    trace_id: str,
    exception: Exception,
    guild_id: Optional[int] = None,
    source_platform: Optional[str] = None,
    input_url: Optional[str] = None,
    ffmpeg_stderr: Optional[str] = None,
    extra_context: Optional[Dict[str, Any]] = None,
    caller_frame: Optional[Any] = None
):
    """Appends a structured JSON error record to logs/error_traces.json."""
    try:
        tb = traceback.extract_tb(exception.__traceback__)
        if tb:
            last_frame = tb[-1]
            file_name = os.path.basename(last_frame.filename)
            func_name = last_frame.name
            line_no = last_frame.lineno
        elif caller_frame:
            file_name = os.path.basename(caller_frame.f_code.co_filename)
            func_name = caller_frame.f_code.co_name
            line_no = caller_frame.f_lineno
        else:
            file_name = "unknown"
            func_name = "unknown"
            line_no = 0

        record = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "trace_id": trace_id,
            "guild_id": guild_id,
            "source_platform": source_platform or "unknown",
            "input_url": input_url or "",
            "file": file_name,
            "function": func_name,
            "line_number": line_no,
            "exception_type": type(exception).__name__,
            "message": str(exception),
            "stack_trace": "".join(traceback.format_exception(type(exception), exception, exception.__traceback__)),
            "ffmpeg_stderr": ffmpeg_stderr or "",
            "extra_context": extra_context or {}
        }

        with open(ERROR_TRACES_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(record) + "\n")

    except Exception as e:
        sys.stderr.write(f"Failed to record error trace: {e}\n")

async def read_ffmpeg_stderr_async(stream_reader: asyncio.StreamReader, trace_id: str, max_lines: int = 50) -> str:
    """Asynchronously consumes FFmpeg stderr lines and captures recent output for diagnosis."""
    collected = []
    try:
        while not stream_reader.at_eof():
            line = await stream_reader.readline()
            if not line:
                break
            text = line.decode("utf-8", errors="replace").rstrip()
            if text:
                collected.append(text)
                if len(collected) > max_lines:
                    collected.pop(0)
                # If error detected in output, log immediately
                if "error" in text.lower() or "403 forbidden" in text.lower() or "failed" in text.lower():
                    log.warning(f"FFmpeg stderr: {text}", extra={"trace_id": trace_id})
    except Exception as e:
        log.warning(f"Error reading FFmpeg stderr: {e}", extra={"trace_id": trace_id})
    return "\n".join(collected)

def trace_and_log(
    platform_name: Optional[str] = None,
    extract_url_arg: Optional[str] = None
):
    """
    Decorator for slash commands and extractors.
    Logs lifecycle steps with trace_id, execution time, and records full JSON error trace on failure.
    """
    def decorator(func: Callable):
        if inspect.iscoroutinefunction(func):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                trace_id = kwargs.get("trace_id") or generate_trace_id()
                kwargs["trace_id"] = trace_id
                t0 = time.time()
                func_name = func.__name__
                input_url = kwargs.get(extract_url_arg) if extract_url_arg else None

                # Find guild_id if first arg is an Interaction or GuildPlayer
                guild_id = None
                if args and hasattr(args[0], "guild") and getattr(args[0], "guild", None):
                    guild_id = args[0].guild.id
                elif len(args) > 1 and hasattr(args[1], "guild") and getattr(args[1], "guild", None):
                    guild_id = args[1].guild.id

                log.info(f"Invoking {func_name}...", extra={"trace_id": trace_id, "guild_id": guild_id})

                try:
                    result = await func(*args, **kwargs)
                    elapsed_ms = (time.time() - t0) * 1000
                    log.info(f"Completed {func_name} successfully in {elapsed_ms:.1f}ms", extra={"trace_id": trace_id, "guild_id": guild_id})
                    return result
                except Exception as exc:
                    elapsed_ms = (time.time() - t0) * 1000
                    log.error(f"Failed in {func_name} after {elapsed_ms:.1f}ms: {exc}", exc_info=True, extra={"trace_id": trace_id, "guild_id": guild_id})
                    record_error_trace(
                        trace_id=trace_id,
                        exception=exc,
                        guild_id=guild_id,
                        source_platform=platform_name,
                        input_url=input_url,
                        caller_frame=inspect.currentframe()
                    )
                    raise exc
            return async_wrapper
        else:
            @functools.wraps(func)
            def sync_wrapper(*args, **kwargs):
                trace_id = kwargs.get("trace_id") or generate_trace_id()
                kwargs["trace_id"] = trace_id
                t0 = time.time()
                func_name = func.__name__
                input_url = kwargs.get(extract_url_arg) if extract_url_arg else None
                guild_id = None

                log.info(f"Invoking {func_name}...", extra={"trace_id": trace_id, "guild_id": guild_id})
                try:
                    result = func(*args, **kwargs)
                    elapsed_ms = (time.time() - t0) * 1000
                    log.info(f"Completed {func_name} successfully in {elapsed_ms:.1f}ms", extra={"trace_id": trace_id, "guild_id": guild_id})
                    return result
                except Exception as exc:
                    elapsed_ms = (time.time() - t0) * 1000
                    log.error(f"Failed in {func_name} after {elapsed_ms:.1f}ms: {exc}", exc_info=True, extra={"trace_id": trace_id, "guild_id": guild_id})
                    record_error_trace(
                        trace_id=trace_id,
                        exception=exc,
                        guild_id=guild_id,
                        source_platform=platform_name,
                        input_url=input_url,
                        caller_frame=inspect.currentframe()
                    )
                    raise exc
            return sync_wrapper
    return decorator
