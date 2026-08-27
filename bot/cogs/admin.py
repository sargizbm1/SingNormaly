"""Admin / general management commands (prefix, DJ role, health check)."""

from __future__ import annotations

import discord
from discord.ext import commands

from bot.database import db
from bot.utils import embeds


class Admin(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @commands.hybrid_command(name="ping", description="Check the bot's latency.")
    async def ping(self, ctx: commands.Context):
        await ctx.send(embed=embeds.success_embed(f"🏓 Pong! `{round(self.bot.latency * 1000)}ms`"))

    @commands.hybrid_command(name="prefix", description="Set the command prefix for this server.")
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def prefix(self, ctx: commands.Context, new_prefix: str):
        if len(new_prefix) > 5:
            return await ctx.send(embed=embeds.error_embed("Prefix must be 5 characters or fewer."))
        await db.set_guild_setting(ctx.guild.id, "prefix", new_prefix)
        await ctx.send(embed=embeds.success_embed(f"Prefix set to `{new_prefix}`."))

    @commands.hybrid_command(name="djrole", description="Set the DJ role required for music controls.")
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def djrole(self, ctx: commands.Context, role: discord.Role | None = None):
        await db.set_guild_setting(ctx.guild.id, "dj_role_id", role.id if role else None)
        msg = f"DJ role set to {role.mention}." if role else "DJ role requirement removed."
        await ctx.send(embed=embeds.success_embed(msg))

    @commands.hybrid_command(name="settings", description="Show this server's current configuration.")
    @commands.has_permissions(manage_guild=True)
    @commands.guild_only()
    async def settings_cmd(self, ctx: commands.Context):
        s = await db.get_guild_settings(ctx.guild.id)
        embed = embeds.base_embed("⚙️ Server Settings")
        embed.add_field(name="Prefix", value=f"`{s['prefix']}`", inline=True)
        embed.add_field(name="Music Volume", value=f"{s['music_volume']}%", inline=True)
        embed.add_field(
            name="Welcome Channel",
            value=f"<#{s['welcome_channel_id']}>" if s["welcome_channel_id"] else "Not set",
            inline=True,
        )
        embed.add_field(
            name="Goodbye Channel",
            value=f"<#{s['goodbye_channel_id']}>" if s["goodbye_channel_id"] else "Not set",
            inline=True,
        )
        embed.add_field(
            name="Log Channel",
            value=f"<#{s['log_channel_id']}>" if s["log_channel_id"] else "Not set",
            inline=True,
        )
        embed.add_field(name="Channel Logging", value="Enabled" if s["log_to_channel"] else "Disabled", inline=True)
        embed.add_field(
            name="DJ Role",
            value=f"<@&{s['dj_role_id']}>" if s["dj_role_id"] else "Anyone",
            inline=True,
        )
        await ctx.send(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Admin(bot))
