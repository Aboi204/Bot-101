import json
import logging
import os
import sys
from datetime import datetime, timezone
from logging.handlers import RotatingFileHandler
from typing import Any, Dict

import config

class JSONFormatter(logging.Formatter):
    """Formats log records as JSON lines conforming to structured diagnostic standards."""

    def format(self, record: logging.LogRecord) -> str:
        log_data: Dict[str, Any] = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Include custom diagnostic fields if provided via extra
        if hasattr(record, "event"):
            log_data["event"] = record.event
        if hasattr(record, "guild_id"):
            log_data["guild_id"] = record.guild_id
        if hasattr(record, "channel_id"):
            log_data["channel_id"] = record.channel_id
        if hasattr(record, "user_id"):
            log_data["user_id"] = record.user_id
        if hasattr(record, "metadata"):
            log_data["metadata"] = record.metadata
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)

class ConsoleFormatter(logging.Formatter):
    """Human-readable console output with ANSI color tags."""
    COLORS = {
        logging.DEBUG: "\033[36m",    # Cyan
        logging.INFO: "\033[32m",     # Green
        logging.WARNING: "\033[33m",  # Yellow
        logging.ERROR: "\033[31m",    # Red
        logging.CRITICAL: "\033[41m", # Red background
    }
    RESET = "\033[0m"

    def format(self, record: logging.LogRecord) -> str:
        color = self.COLORS.get(record.levelno, self.RESET)
        time_str = datetime.now().strftime("%H:%M:%S")
        event_str = f" [{record.event}]" if hasattr(record, "event") else ""
        base = f"{color}[{time_str}] [{record.levelname:<7}] [{record.name}]{event_str} {record.getMessage()}{self.RESET}"
        if record.exc_info:
            base += "\n" + self.formatException(record.exc_info)
        return base

def setup_logger(name: str = "discord_bot") -> logging.Logger:
    """Configures root application logger with rotating file and console handlers."""
    logger = logging.getLogger(name)
    logger.setLevel(getattr(logging, config.LOG_LEVEL, logging.INFO))
    logger.handlers.clear()

    # Console Handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(ConsoleFormatter())
    logger.addHandler(console_handler)

    # Rotating File Handler
    try:
        file_handler = RotatingFileHandler(
            config.LOG_FILE,
            maxBytes=10 * 1024 * 1024,  # 10 MB
            backupCount=5,
            encoding="utf-8"
        )
        if config.JSON_LOGS:
            file_handler.setFormatter(JSONFormatter())
        else:
            file_handler.setFormatter(logging.Formatter(
                "%(asctime)s [%(levelname)s] [%(name)s] %(message)s"
            ))
        logger.addHandler(file_handler)
    except Exception as e:
        sys.stderr.write(f"Failed to initialize log file handler: {e}\n")

    return logger

log = setup_logger()
