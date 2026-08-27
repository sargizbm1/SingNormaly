"""Small reusable permission checks."""

from __future__ import annotations

import discord
from discord.ext import commands

from bot.database import db


async def is_dj_or_admin(ctx: commands.Context) -> bool:
    """DJ role (per-guild, configurable) or Manage Server permission."""
    if ctx.author.guild_permissions.manage_guild:
        return True
    settings = await db.get_guild_settings(ctx.guild.id)
    dj_role_id = settings.get("dj_role_id")
    if dj_role_id and any(r.id == dj_role_id for r in ctx.author.roles):
        return True
    # If no DJ role configured, allow anyone (keeps small servers frictionless).
    return dj_role_id is None


def in_same_voice_channel():
    async def predicate(ctx: commands.Context) -> bool:
        voice_client: discord.VoiceClient | None = ctx.guild.voice_client
        author_voice = ctx.author.voice
        if voice_client is None:
            return True  # bot not connected yet, command handler will connect
        if author_voice is None or author_voice.channel != voice_client.channel:
            raise commands.CheckFailure("You must be in the same voice channel as the bot.")
        return True

    return commands.check(predicate)
