"""
Logging cog.

Mirrors log records (from bot.logger.discord_log_handler) into a
per-guild log channel, if the guild has enabled `log_to_channel` and set
a `log_channel_id`. Full-detail logs always go to the rotating file on
disk regardless of this setting (see bot/logger.py).

Also logs command usage and important lifecycle/member events, and
records every invoked command to the database for auditing.
"""

from __future__ import annotations

import asyncio
import logging

import discord
from discord.ext import commands

from bot.database import db
from bot.logger import discord_log_handler
from bot.utils import embeds

log = logging.getLogger("bot.events")


class Logging(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self._drain_task: asyncio.Task | None = None

    async def cog_load(self) -> None:
        self._drain_task = self.bot.loop.create_task(self._drain_log_queue())

    async def cog_unload(self) -> None:
        if self._drain_task:
            self._drain_task.cancel()

    async def _drain_log_queue(self) -> None:
        """Continuously forwards queued log lines to every guild that has
        opted in to channel logging."""
        await self.bot.wait_until_ready()
        while True:
            line = await discord_log_handler.queue.get()
            for guild in self.bot.guilds:
                try:
                    settings = await db.get_guild_settings(guild.id)
                except Exception:  # noqa: BLE001
                    continue
                if not settings.get("log_to_channel") or not settings.get("log_channel_id"):
                    continue
                channel = guild.get_channel(settings["log_channel_id"])
                if channel is None:
                    continue
                try:
                    await channel.send(f"```{line[:1900]}```")
                except discord.Forbidden:
                    log.warning("Missing permission to post logs in guild %s", guild.id)
                except discord.HTTPException:
                    pass

    # ---------- lifecycle events ----------

    @commands.Cog.listener()
    async def on_ready(self):
        log.info("Logged in as %s (ID: %s)", self.bot.user, self.bot.user.id)

    @commands.Cog.listener()
    async def on_command(self, ctx: commands.Context):
        log.info(
            "Command '%s' invoked by %s in guild %s",
            ctx.command,
            ctx.author,
            ctx.guild.id if ctx.guild else "DM",
        )
        if ctx.guild:
            await db.log_command(ctx.guild.id, ctx.author.id, str(ctx.command))

    @commands.Cog.listener()
    async def on_command_error(self, ctx: commands.Context, error: commands.CommandError):
        if isinstance(error, commands.CheckFailure):
            await ctx.send(embed=embeds.error_embed(str(error) or "You can't do that."))
            return
        if isinstance(error, commands.CommandNotFound):
            return
        if isinstance(error, commands.MissingRequiredArgument):
            await ctx.send(embed=embeds.error_embed(f"Missing argument: `{error.param.name}`."))
            return
        log.exception("Unhandled error in command '%s'", ctx.command, exc_info=error)
        await ctx.send(embed=embeds.error_embed("Something went wrong running that command."))

    @commands.Cog.listener()
    async def on_guild_join(self, guild: discord.Guild):
        log.info("Joined guild '%s' (ID: %s)", guild.name, guild.id)

    @commands.Cog.listener()
    async def on_guild_remove(self, guild: discord.Guild):
        log.info("Removed from guild '%s' (ID: %s)", guild.name, guild.id)

    # ---------- configuration commands ----------

    @commands.hybrid_group(name="logs", description="Configure the Discord log channel.")
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def logs_group(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @logs_group.command(name="channel", description="Set the log channel.")
    async def logs_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        await db.set_guild_setting(ctx.guild.id, "log_channel_id", channel.id)
        await ctx.send(embed=embeds.success_embed(f"Log channel set to {channel.mention}."))

    @logs_group.command(name="enable", description="Enable mirroring logs to the log channel.")
    async def logs_enable(self, ctx: commands.Context):
        await db.set_guild_setting(ctx.guild.id, "log_to_channel", 1)
        await ctx.send(embed=embeds.success_embed("Channel logging enabled."))

    @logs_group.command(name="disable", description="Disable mirroring logs to the log channel.")
    async def logs_disable(self, ctx: commands.Context):
        await db.set_guild_setting(ctx.guild.id, "log_to_channel", 0)
        await ctx.send(embed=embeds.success_embed("Channel logging disabled."))


async def setup(bot: commands.Bot):
    await bot.add_cog(Logging(bot))
