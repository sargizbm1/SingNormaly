"""
Welcome / Goodbye cog.

Messages support placeholders:
  {mention}        -> user mention
  {user}           -> username
  {tag}             -> username#discriminator (or new-style username)
  {guild}          -> server name
  {member_count}   -> current member count
"""

from __future__ import annotations

import logging

import discord
from discord.ext import commands

from bot.database import db
from bot.utils import embeds

log = logging.getLogger("bot.welcome")


def _format(template: str, member: discord.Member) -> str:
    return template.format(
        mention=member.mention,
        user=member.name,
        tag=str(member),
        guild=member.guild.name,
        member_count=member.guild.member_count,
    )


class Welcome(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member):
        settings = await db.get_guild_settings(member.guild.id)
        channel_id = settings.get("welcome_channel_id")
        if not channel_id:
            return
        channel = member.guild.get_channel(channel_id)
        if channel is None:
            return

        text = _format(settings["welcome_message"], member)
        embed = embeds.base_embed("👋 New Member", text, embeds.COLOR_SUCCESS)
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"Member #{member.guild.member_count}")
        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            log.warning("Missing permission to send welcome message in guild %s", member.guild.id)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member):
        settings = await db.get_guild_settings(member.guild.id)
        channel_id = settings.get("goodbye_channel_id")
        if not channel_id:
            return
        channel = member.guild.get_channel(channel_id)
        if channel is None:
            return

        text = _format(settings["goodbye_message"], member)
        embed = embeds.base_embed("👋 Member Left", text, embeds.COLOR_WARN)
        embed.set_thumbnail(url=member.display_avatar.url)
        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            log.warning("Missing permission to send goodbye message in guild %s", member.guild.id)

    # ---------- configuration commands ----------

    @commands.hybrid_group(name="welcome", description="Configure welcome messages.")
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def welcome_group(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @welcome_group.command(name="channel", description="Set the welcome channel.")
    async def welcome_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        await db.set_guild_setting(ctx.guild.id, "welcome_channel_id", channel.id)
        await ctx.send(embed=embeds.success_embed(f"Welcome channel set to {channel.mention}."))

    @welcome_group.command(name="message", description="Set the welcome message template.")
    async def welcome_message(self, ctx: commands.Context, *, template: str):
        await db.set_guild_setting(ctx.guild.id, "welcome_message", template)
        await ctx.send(embed=embeds.success_embed("Welcome message updated."))

    @commands.hybrid_group(name="goodbye", description="Configure goodbye messages.")
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def goodbye_group(self, ctx: commands.Context):
        if ctx.invoked_subcommand is None:
            await ctx.send_help(ctx.command)

    @goodbye_group.command(name="channel", description="Set the goodbye channel.")
    async def goodbye_channel(self, ctx: commands.Context, channel: discord.TextChannel):
        await db.set_guild_setting(ctx.guild.id, "goodbye_channel_id", channel.id)
        await ctx.send(embed=embeds.success_embed(f"Goodbye channel set to {channel.mention}."))

    @goodbye_group.command(name="message", description="Set the goodbye message template.")
    async def goodbye_message(self, ctx: commands.Context, *, template: str):
        await db.set_guild_setting(ctx.guild.id, "goodbye_message", template)
        await ctx.send(embed=embeds.success_embed("Goodbye message updated."))


async def setup(bot: commands.Bot):
    await bot.add_cog(Welcome(bot))
