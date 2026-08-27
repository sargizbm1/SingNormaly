"""
Entry point. Run with: python -m bot.main
"""

from __future__ import annotations

import asyncio
import logging

import discord
from discord.ext import commands

from bot.config import config
from bot.database import db
from bot.logger import setup_logging

log = setup_logging()

INTENTS = discord.Intents.default()
INTENTS.message_content = True
INTENTS.members = True  # required for welcome/goodbye events
INTENTS.voice_states = True  # required for music playback

INITIAL_EXTENSIONS = [
    "bot.cogs.music",
    "bot.cogs.welcome",
    "bot.cogs.logging_cog",
    "bot.cogs.admin",
]


async def get_prefix(bot: commands.Bot, message: discord.Message):
    if message.guild is None:
        return commands.when_mentioned_or(config.default_prefix)(bot, message)
    settings = await db.get_guild_settings(message.guild.id)
    return commands.when_mentioned_or(settings["prefix"])(bot, message)


class MusicBot(commands.Bot):
    def __init__(self):
        super().__init__(command_prefix=get_prefix, intents=INTENTS, help_command=commands.DefaultHelpCommand())

    async def setup_hook(self) -> None:
        await db.connect()
        for extension in INITIAL_EXTENSIONS:
            try:
                await self.load_extension(extension)
                log.info("Loaded extension: %s", extension)
            except Exception:
                log.exception("Failed to load extension: %s", extension)
        await self.tree.sync()

    async def close(self) -> None:
        await db.close()
        await super().close()


bot = MusicBot()


async def main():
    async with bot:
        await bot.start(config.token)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        log.info("Shutdown requested by user.")
