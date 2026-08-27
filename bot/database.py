"""
Async SQLite database layer.

Single file (data/bot.db by default) so backup/migration to a new host is
just "copy the file". Stores one row per guild with all per-server
settings (prefix, welcome/goodbye/log channels, music defaults, etc).
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import aiosqlite

from bot.config import config

SCHEMA = """
CREATE TABLE IF NOT EXISTS guild_settings (
    guild_id            INTEGER PRIMARY KEY,
    prefix              TEXT DEFAULT '!',
    welcome_channel_id  INTEGER,
    goodbye_channel_id  INTEGER,
    log_channel_id      INTEGER,
    log_to_channel      INTEGER DEFAULT 0,     -- 0/1 toggle, mirrors logs to log_channel_id
    welcome_message     TEXT,
    goodbye_message     TEXT,
    dj_role_id          INTEGER,
    music_volume        INTEGER DEFAULT 100,
    extra_json          TEXT DEFAULT '{}'      -- free-form bucket for future settings
);

CREATE TABLE IF NOT EXISTS command_log (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    guild_id    INTEGER,
    user_id     INTEGER,
    command     TEXT,
    created_at  TEXT DEFAULT CURRENT_TIMESTAMP
);
"""

DEFAULTS: dict[str, Any] = {
    "prefix": config.default_prefix,
    "welcome_channel_id": None,
    "goodbye_channel_id": None,
    "log_channel_id": None,
    "log_to_channel": 0,
    "welcome_message": "Welcome {mention} to **{guild}**! You're member #{member_count}.",
    "goodbye_message": "**{user}** has left **{guild}**. See you around!",
    "dj_role_id": None,
    "music_volume": 100,
    "extra_json": "{}",
}


class Database:
    def __init__(self, path: str | None = None):
        self.path = path or config.database_path
        Path(self.path).parent.mkdir(parents=True, exist_ok=True)
        self._conn: aiosqlite.Connection | None = None

    async def connect(self) -> None:
        self._conn = await aiosqlite.connect(self.path)
        self._conn.row_factory = aiosqlite.Row
        await self._conn.executescript(SCHEMA)
        await self._conn.commit()

    async def close(self) -> None:
        if self._conn:
            await self._conn.close()

    @property
    def conn(self) -> aiosqlite.Connection:
        if self._conn is None:
            raise RuntimeError("Database not connected. Call connect() first.")
        return self._conn

    async def _ensure_row(self, guild_id: int) -> None:
        await self.conn.execute(
            "INSERT OR IGNORE INTO guild_settings (guild_id) VALUES (?)", (guild_id,)
        )
        await self.conn.commit()

    async def get_guild_settings(self, guild_id: int) -> dict[str, Any]:
        await self._ensure_row(guild_id)
        cursor = await self.conn.execute(
            "SELECT * FROM guild_settings WHERE guild_id = ?", (guild_id,)
        )
        row = await cursor.fetchone()
        data = dict(row)
        data["extra"] = json.loads(data.pop("extra_json") or "{}")
        return data

    async def set_guild_setting(self, guild_id: int, key: str, value: Any) -> None:
        if key not in DEFAULTS:
            raise ValueError(f"Unknown guild setting: {key}")
        await self._ensure_row(guild_id)
        await self.conn.execute(
            f"UPDATE guild_settings SET {key} = ? WHERE guild_id = ?", (value, guild_id)
        )
        await self.conn.commit()

    async def set_extra(self, guild_id: int, key: str, value: Any) -> None:
        settings = await self.get_guild_settings(guild_id)
        extra = settings["extra"]
        extra[key] = value
        await self.conn.execute(
            "UPDATE guild_settings SET extra_json = ? WHERE guild_id = ?",
            (json.dumps(extra), guild_id),
        )
        await self.conn.commit()

    async def log_command(self, guild_id: int | None, user_id: int, command: str) -> None:
        await self.conn.execute(
            "INSERT INTO command_log (guild_id, user_id, command) VALUES (?, ?, ?)",
            (guild_id, user_id, command),
        )
        await self.conn.commit()


db = Database()
