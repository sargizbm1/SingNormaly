"""Reusable embed builders so every cog has a consistent, professional look."""

from __future__ import annotations

import discord

COLOR_PRIMARY = discord.Color.blurple()
COLOR_SUCCESS = discord.Color.green()
COLOR_ERROR = discord.Color.red()
COLOR_WARN = discord.Color.gold()


def base_embed(title: str, description: str = "", color: discord.Color = COLOR_PRIMARY) -> discord.Embed:
    embed = discord.Embed(title=title, description=description, color=color)
    return embed


def success_embed(description: str, title: str = "Success") -> discord.Embed:
    return base_embed(title, description, COLOR_SUCCESS)


def error_embed(description: str, title: str = "Error") -> discord.Embed:
    return base_embed(title, description, COLOR_ERROR)


def now_playing_embed(track, requester: discord.Member) -> discord.Embed:
    embed = base_embed("🎶 Now Playing", f"**[{track.title}]({track.uri})**")
    embed.add_field(name="Author", value=track.author or "Unknown", inline=True)
    length_s = (track.length or 0) // 1000
    embed.add_field(name="Duration", value=f"{length_s // 60}:{length_s % 60:02d}", inline=True)
    embed.add_field(name="Requested by", value=requester.mention, inline=True)
    if getattr(track, "artwork", None):
        embed.set_thumbnail(url=track.artwork)
    return embed


def queue_embed(tracks: list, page: int = 1, per_page: int = 10) -> discord.Embed:
    start = (page - 1) * per_page
    chunk = tracks[start : start + per_page]
    if not chunk:
        return base_embed("📜 Queue", "The queue is empty.")
    lines = [f"`{start + i + 1}.` {t.title} — {t.author}" for i, t in enumerate(chunk)]
    embed = base_embed("📜 Queue", "\n".join(lines))
    total_pages = max(1, -(-len(tracks) // per_page))
    embed.set_footer(text=f"Page {page}/{total_pages} • {len(tracks)} track(s) queued")
    return embed
