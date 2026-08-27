"""
Music cog.

Playback runs through Lavalink (via wavelink), which is the standard,
ToS-compliant way to run a Discord music bot: audio itself is streamed
from YouTube/SoundCloud/etc, while Spotify links/playlists are resolved
for their *metadata* (title/artist) and then matched to a playable source.
This is how essentially every stable "Spotify support" Discord bot works,
since Spotify's own audio streams cannot be redistributed by third-party
bots.

If your Lavalink server has the LavaSrc plugin configured with Spotify
credentials (see lavalink/application.yml), wavelink will resolve
open.spotify.com links natively. Otherwise this cog falls back to
searching YouTube using the track's title + author pulled from Spotify's
public API via spotipy.
"""

from __future__ import annotations

import logging
import re

import discord
import spotipy
import wavelink
from discord.ext import commands
from spotipy.oauth2 import SpotifyClientCredentials

from bot.config import config
from bot.database import db
from bot.utils import embeds
from bot.utils.checks import is_dj_or_admin

log = logging.getLogger("bot.music")

SPOTIFY_URL_RE = re.compile(
    r"open\.spotify\.com/(?:intl-\w+/)?(track|album|playlist)/([A-Za-z0-9]+)"
)


class Music(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.spotify: spotipy.Spotify | None = None
        if config.spotify.enabled:
            self.spotify = spotipy.Spotify(
                auth_manager=SpotifyClientCredentials(
                    client_id=config.spotify.client_id,
                    client_secret=config.spotify.client_secret,
                )
            )

    # ---------- lifecycle ----------

    async def cog_load(self) -> None:
        node = wavelink.Node(
            uri=config.lavalink.uri,
            password=config.lavalink.password,
        )
        await wavelink.Pool.connect(nodes=[node], client=self.bot)
        log.info("Connected to Lavalink node at %s", config.lavalink.uri)

    @commands.Cog.listener()
    async def on_wavelink_node_ready(self, payload: wavelink.NodeReadyEventPayload) -> None:
        log.info("Lavalink node '%s' is ready (session=%s)", payload.node.identifier, payload.session_id)

    @commands.Cog.listener()
    async def on_wavelink_track_start(self, payload: wavelink.TrackStartEventPayload) -> None:
        player: wavelink.Player = payload.player
        channel = getattr(player, "text_channel", None)
        if channel:
            requester = getattr(payload.track, "extras", {}).get("requester_id")
            member = channel.guild.get_member(requester) if requester else None
            embed = embeds.now_playing_embed(payload.track, member or channel.guild.me)
            await channel.send(embed=embed, view=PlayerControls(player))

    @commands.Cog.listener()
    async def on_wavelink_track_end(self, payload: wavelink.TrackEndEventPayload) -> None:
        player: wavelink.Player = payload.player
        if player.queue.is_empty and not player.playing:
            # Auto-disconnect after the queue drains to free the voice slot.
            await player.disconnect()

    # ---------- helpers ----------

    async def _ensure_voice(self, ctx: commands.Context) -> wavelink.Player | None:
        if ctx.author.voice is None or ctx.author.voice.channel is None:
            await ctx.send(embed=embeds.error_embed("You must join a voice channel first."))
            return None

        player: wavelink.Player | None = ctx.voice_client  # type: ignore[assignment]
        if player is None:
            player = await ctx.author.voice.channel.connect(cls=wavelink.Player)
            player.text_channel = ctx.channel  # type: ignore[attr-defined]
            settings = await db.get_guild_settings(ctx.guild.id)
            await player.set_volume(settings["music_volume"])
        return player

    async def _resolve_query(self, query: str) -> list[wavelink.Playable]:
        spotify_match = SPOTIFY_URL_RE.search(query)
        if spotify_match and self.spotify:
            kind, item_id = spotify_match.groups()
            return await self._resolve_spotify(kind, item_id)

        # Direct search on Lavalink (handles YouTube/SoundCloud links and
        # plain text search terms, and Spotify links directly if LavaSrc
        # is configured on the Lavalink server).
        results = await wavelink.Playable.search(query)
        if isinstance(results, wavelink.Playlist):
            return list(results.tracks)
        return list(results[:1]) if results else []

    async def _resolve_spotify(self, kind: str, item_id: str) -> list[wavelink.Playable]:
        tracks: list[wavelink.Playable] = []
        if kind == "track":
            meta = self.spotify.track(item_id)
            found = await self._search_one(meta["name"], meta["artists"][0]["name"])
            if found:
                tracks.append(found)
        elif kind in {"album", "playlist"}:
            getter = self.spotify.album_tracks if kind == "album" else self.spotify.playlist_items
            offset = 0
            while True:
                page = getter(item_id, offset=offset)
                items = page["items"]
                if not items:
                    break
                for item in items:
                    meta = item["track"] if kind == "playlist" else item
                    if not meta:
                        continue
                    found = await self._search_one(meta["name"], meta["artists"][0]["name"])
                    if found:
                        tracks.append(found)
                offset += len(items)
                if page.get("next") is None:
                    break
        return tracks

    @staticmethod
    async def _search_one(title: str, artist: str) -> wavelink.Playable | None:
        results = await wavelink.Playable.search(f"{title} {artist}")
        if isinstance(results, wavelink.Playlist):
            return results.tracks[0] if results.tracks else None
        return results[0] if results else None

    # ---------- commands ----------

    @commands.hybrid_command(name="play", description="Play a song or playlist from Spotify, YouTube, etc.")
    @commands.guild_only()
    async def play(self, ctx: commands.Context, *, query: str):
        await ctx.defer()
        player = await self._ensure_voice(ctx)
        if player is None:
            return

        tracks = await self._resolve_query(query)
        if not tracks:
            await ctx.send(embed=embeds.error_embed(f"No results found for **{query}**."))
            return

        for track in tracks:
            track.extras = {"requester_id": ctx.author.id}
            await player.queue.put_wait(track)

        if not player.playing:
            await player.play(player.queue.get())

        if len(tracks) == 1:
            await ctx.send(embed=embeds.success_embed(f"Queued **{tracks[0].title}**."))
        else:
            await ctx.send(embed=embeds.success_embed(f"Queued **{len(tracks)}** tracks."))

    @commands.hybrid_command(name="pause", description="Pause the current track.")
    @commands.guild_only()
    @commands.check(is_dj_or_admin)
    async def pause(self, ctx: commands.Context):
        player: wavelink.Player | None = ctx.voice_client  # type: ignore[assignment]
        if not player or not player.playing:
            return await ctx.send(embed=embeds.error_embed("Nothing is playing."))
        await player.pause(True)
        await ctx.send(embed=embeds.success_embed("⏸️ Paused."))

    @commands.hybrid_command(name="resume", description="Resume playback.")
    @commands.guild_only()
    @commands.check(is_dj_or_admin)
    async def resume(self, ctx: commands.Context):
        player: wavelink.Player | None = ctx.voice_client  # type: ignore[assignment]
        if not player or not player.paused:
            return await ctx.send(embed=embeds.error_embed("Playback is not paused."))
        await player.pause(False)
        await ctx.send(embed=embeds.success_embed("▶️ Resumed."))

    @commands.hybrid_command(name="skip", description="Skip the current track.")
    @commands.guild_only()
    @commands.check(is_dj_or_admin)
    async def skip(self, ctx: commands.Context):
        player: wavelink.Player | None = ctx.voice_client  # type: ignore[assignment]
        if not player or not player.playing:
            return await ctx.send(embed=embeds.error_embed("Nothing is playing."))
        await player.skip(force=True)
        await ctx.send(embed=embeds.success_embed("⏭️ Skipped."))

    @commands.hybrid_command(name="stop", description="Stop playback and clear the queue.")
    @commands.guild_only()
    @commands.check(is_dj_or_admin)
    async def stop(self, ctx: commands.Context):
        player: wavelink.Player | None = ctx.voice_client  # type: ignore[assignment]
        if not player:
            return await ctx.send(embed=embeds.error_embed("I'm not connected to a voice channel."))
        player.queue.clear()
        await player.stop()
        await player.disconnect()
        await ctx.send(embed=embeds.success_embed("⏹️ Stopped and left the voice channel."))

    @commands.hybrid_command(name="queue", description="Show the current queue.")
    @commands.guild_only()
    async def queue_cmd(self, ctx: commands.Context, page: int = 1):
        player: wavelink.Player | None = ctx.voice_client  # type: ignore[assignment]
        if not player or player.queue.is_empty:
            return await ctx.send(embed=embeds.base_embed("📜 Queue", "The queue is empty."))
        await ctx.send(embed=embeds.queue_embed(list(player.queue), page=page))

    @commands.hybrid_command(name="nowplaying", description="Show the currently playing track.")
    @commands.guild_only()
    async def nowplaying(self, ctx: commands.Context):
        player: wavelink.Player | None = ctx.voice_client  # type: ignore[assignment]
        if not player or not player.current:
            return await ctx.send(embed=embeds.error_embed("Nothing is playing."))
        await ctx.send(embed=embeds.now_playing_embed(player.current, ctx.author))

    @commands.hybrid_command(name="volume", description="Set playback volume (0-150).")
    @commands.guild_only()
    @commands.check(is_dj_or_admin)
    async def volume(self, ctx: commands.Context, level: int):
        level = max(0, min(150, level))
        player: wavelink.Player | None = ctx.voice_client  # type: ignore[assignment]
        if not player:
            return await ctx.send(embed=embeds.error_embed("I'm not connected to a voice channel."))
        await player.set_volume(level)
        await db.set_guild_setting(ctx.guild.id, "music_volume", level)
        await ctx.send(embed=embeds.success_embed(f"🔊 Volume set to {level}%."))

    @commands.hybrid_command(name="leave", description="Disconnect the bot from voice.")
    @commands.guild_only()
    @commands.check(is_dj_or_admin)
    async def leave(self, ctx: commands.Context):
        player: wavelink.Player | None = ctx.voice_client  # type: ignore[assignment]
        if not player:
            return await ctx.send(embed=embeds.error_embed("I'm not connected to a voice channel."))
        await player.disconnect()
        await ctx.send(embed=embeds.success_embed("👋 Disconnected."))


class PlayerControls(discord.ui.View):
    """Buttons attached to the now-playing message for quick control."""

    def __init__(self, player: wavelink.Player):
        super().__init__(timeout=None)
        self.player = player

    @discord.ui.button(emoji="⏯️", style=discord.ButtonStyle.primary)
    async def pause_resume(self, interaction: discord.Interaction, _: discord.ui.Button):
        await self.player.pause(not self.player.paused)
        await interaction.response.send_message(
            "⏸️ Paused." if self.player.paused else "▶️ Resumed.", ephemeral=True
        )

    @discord.ui.button(emoji="⏭️", style=discord.ButtonStyle.secondary)
    async def skip(self, interaction: discord.Interaction, _: discord.ui.Button):
        await self.player.skip(force=True)
        await interaction.response.send_message("⏭️ Skipped.", ephemeral=True)

    @discord.ui.button(emoji="⏹️", style=discord.ButtonStyle.danger)
    async def stop(self, interaction: discord.Interaction, _: discord.ui.Button):
        self.player.queue.clear()
        await self.player.stop()
        await self.player.disconnect()
        await interaction.response.send_message("⏹️ Stopped.", ephemeral=True)


async def setup(bot: commands.Bot):
    await bot.add_cog(Music(bot))
