"""
Central configuration module.

All secrets / environment-dependent values are loaded from environment
variables (via a .env file in development, or real environment variables
in production / Docker / systemd). Nothing sensitive is hard-coded, so the
project can be moved to a new host by only changing the .env file.
"""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

# Load .env from project root (safe no-op if the file doesn't exist, e.g.
# when real environment variables are injected by Docker/systemd instead).
BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def _get_bool(name: str, default: bool = False) -> bool:
    val = os.getenv(name)
    if val is None:
        return default
    return val.strip().lower() in {"1", "true", "yes", "on"}


def _require(name: str) -> str:
    val = os.getenv(name)
    if not val:
        raise RuntimeError(
            f"Missing required environment variable '{name}'. "
            f"Copy .env.example to .env and fill it in."
        )
    return val


@dataclass(frozen=True)
class LavalinkConfig:
    host: str = field(default_factory=lambda: os.getenv("LAVALINK_HOST", "127.0.0.1"))
    port: int = field(default_factory=lambda: int(os.getenv("LAVALINK_PORT", "2333")))
    password: str = field(default_factory=lambda: os.getenv("LAVALINK_PASSWORD", "youshallnotpass"))
    secure: bool = field(default_factory=lambda: _get_bool("LAVALINK_SECURE", False))

    @property
    def uri(self) -> str:
        scheme = "https" if self.secure else "http"
        return f"{scheme}://{self.host}:{self.port}"


@dataclass(frozen=True)
class SpotifyConfig:
    client_id: str | None = field(default_factory=lambda: os.getenv("SPOTIFY_CLIENT_ID") or None)
    client_secret: str | None = field(default_factory=lambda: os.getenv("SPOTIFY_CLIENT_SECRET") or None)

    @property
    def enabled(self) -> bool:
        return bool(self.client_id and self.client_secret)


@dataclass(frozen=True)
class Config:
    token: str = field(default_factory=lambda: _require("DISCORD_TOKEN"))
    default_prefix: str = field(default_factory=lambda: os.getenv("DEFAULT_PREFIX", "!"))
    database_path: str = field(default_factory=lambda: os.getenv("DATABASE_PATH", "data/bot.db"))
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))
    log_dir: str = field(default_factory=lambda: os.getenv("LOG_DIR", "logs"))
    lavalink: LavalinkConfig = field(default_factory=LavalinkConfig)
    spotify: SpotifyConfig = field(default_factory=SpotifyConfig)


config = Config()
