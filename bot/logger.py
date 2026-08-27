"""
Logging setup.

- Console output: colored, human friendly.
- File output: rotating file, always full detail (kept on disk regardless
  of what is mirrored to Discord).
- Discord channel output: a lightweight in-memory queue that cogs/admin.py
  drains into a configured log channel per guild, so channel verbosity
  can be controlled independently from file verbosity (see cogs/logging_cog.py).
"""

from __future__ import annotations

import asyncio
import logging
import logging.handlers
from pathlib import Path

import colorlog

from bot.config import config

LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"


class DiscordLogQueueHandler(logging.Handler):
    """Pushes formatted log records into an asyncio.Queue that a Discord
    cog can consume and forward to a per-guild log channel. Kept separate
    from the file handler so channel verbosity can be tuned independently.
    """

    def __init__(self, level: int = logging.INFO):
        super().__init__(level=level)
        self.queue: asyncio.Queue[str] = asyncio.Queue(maxsize=500)

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            if self.queue.full():
                # Drop oldest to avoid unbounded growth / crashing on backpressure.
                self.queue.get_nowait()
            self.queue.put_nowait(msg)
        except Exception:  # noqa: BLE001 - logging must never crash the bot
            self.handleError(record)


discord_log_handler = DiscordLogQueueHandler(level=logging.INFO)


def setup_logging() -> logging.Logger:
    log_dir = Path(config.log_dir)
    log_dir.mkdir(parents=True, exist_ok=True)

    root = logging.getLogger()
    root.setLevel(config.log_level.upper())

    # Avoid duplicate handlers if setup_logging() is called more than once.
    if root.handlers:
        return logging.getLogger("bot")

    console_handler = colorlog.StreamHandler()
    console_handler.setFormatter(
        colorlog.ColoredFormatter(
            "%(log_color)s" + LOG_FORMAT,
            datefmt=DATE_FORMAT,
            log_colors={
                "DEBUG": "cyan",
                "INFO": "green",
                "WARNING": "yellow",
                "ERROR": "red",
                "CRITICAL": "bold_red",
            },
        )
    )

    file_handler = logging.handlers.RotatingFileHandler(
        filename=log_dir / "bot.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))

    discord_log_handler.setFormatter(logging.Formatter("%(message)s"))

    root.addHandler(console_handler)
    root.addHandler(file_handler)
    root.addHandler(discord_log_handler)

    # Quiet down noisy third-party loggers.
    logging.getLogger("discord").setLevel(logging.WARNING)
    logging.getLogger("discord.http").setLevel(logging.WARNING)
    logging.getLogger("wavelink").setLevel(logging.INFO)

    return logging.getLogger("bot")
