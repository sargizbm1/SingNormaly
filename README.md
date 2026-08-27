# Discord Music Bot

A professional, modular Discord music bot built in Python (py-cord) with:

- 🎵 Music playback via **Lavalink** (YouTube/SoundCloud/etc audio, with
  **Spotify** link/playlist support resolved through Spotify's metadata API
  and matched to a playable audio source — this is the standard, ToS-safe
  way any Discord bot supports Spotify, since Spotify's own audio streams
  can't be redistributed by third parties)
- ⏯️ Play / Pause / Resume / Skip / Stop / Volume / Queue, with button controls
- 📋 Configurable logging: full detail to rotating log files always, and
  optionally mirrored to a Discord channel per server
- 👋 Welcome / Goodbye messages with customizable templates and embeds
- 🗂️ Per-guild settings stored in SQLite (prefix, channels, DJ role, etc.)
- 🐳 Docker + `docker-compose`, or a `systemd` unit for a bare VPS
- 🔐 No secrets hard-coded — everything sensitive comes from `.env`

---

## Project layout

```
discord-music-bot/
├── bot/
│   ├── main.py            # entry point
│   ├── config.py          # loads & validates .env
│   ├── database.py        # SQLite (per-guild settings)
│   ├── logger.py          # console + file + Discord-channel logging
│   ├── cogs/
│   │   ├── music.py        # playback, queue, Spotify resolution
│   │   ├── welcome.py       # welcome/goodbye messages
│   │   ├── logging_cog.py  # log channel mirroring, command logging
│   │   └── admin.py        # prefix, DJ role, settings, ping
│   └── utils/
│       ├── embeds.py       # shared embed builders
│       └── checks.py       # permission checks
├── lavalink/application.yml  # Lavalink server config (Spotify plugin)
├── systemd/discord-music-bot.service
├── docker-compose.yml
├── Dockerfile
├── requirements.txt
├── .env.example
└── data/                    # SQLite DB lives here (created automatically)
```

---

## 1. Prerequisites

- A Discord bot application + token: https://discord.com/developers/applications
  - Enable **Message Content**, **Server Members**, and (optionally)
    **Presence** intents under Bot → Privileged Gateway Intents.
  - Invite the bot with the `bot` and `applications.commands` scopes and at
    least: View Channels, Send Messages, Embed Links, Connect, Speak.
- (Optional, for Spotify link support) a Spotify app: https://developer.spotify.com/dashboard
  → gives you a Client ID and Client Secret.
- Ubuntu 22.04+ VPS (or any Linux host) with either **Docker** or plain
  **Python 3.11+**.

---

## 2. Configure

```bash
cp .env.example .env
nano .env
```

Fill in at minimum `DISCORD_TOKEN`. Fill in `SPOTIFY_CLIENT_ID` /
`SPOTIFY_CLIENT_SECRET` if you want Spotify link/playlist support.
`LAVALINK_PASSWORD` must match the password set in `lavalink/application.yml`
(same default in both files — change it in both if you customize it).

---

## 3. Run with Docker (recommended)

This starts both the bot and its own Lavalink audio server in one command —
nothing else to install.

```bash
sudo apt update && sudo apt install -y docker.io docker-compose-plugin
sudo docker compose up -d --build
sudo docker compose logs -f bot
```

To stop: `sudo docker compose down`
To update after pulling new code: `sudo docker compose up -d --build`

---

## 4. Run directly on Ubuntu (no Docker)

### 4.1 Install Lavalink (audio backend)

```bash
sudo apt update && sudo apt install -y openjdk-17-jre-headless
mkdir -p ~/lavalink && cd ~/lavalink
curl -L -o Lavalink.jar https://github.com/lavalink-devs/Lavalink/releases/latest/download/Lavalink.jar
cp ~/discord-music-bot/lavalink/application.yml .
java -jar Lavalink.jar
```

Run this in a `systemd` service or `screen`/`tmux` session so it stays up.
A minimal systemd unit:

```ini
[Unit]
Description=Lavalink
After=network.target

[Service]
User=botuser
WorkingDirectory=/home/botuser/lavalink
ExecStart=/usr/bin/java -jar Lavalink.jar
Restart=on-failure

[Install]
WantedBy=multi-user.target
```

### 4.2 Install and run the bot

```bash
git clone <your-repo-url> discord-music-bot
cd discord-music-bot
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env   # fill it in, see step 2
python -m bot.main
```

### 4.3 Keep it running with systemd

```bash
sudo cp systemd/discord-music-bot.service /etc/systemd/system/
sudo nano /etc/systemd/system/discord-music-bot.service   # fix User/paths
sudo systemctl daemon-reload
sudo systemctl enable --now discord-music-bot
sudo systemctl status discord-music-bot
journalctl -u discord-music-bot -f
```

---

## 5. Bot commands (default prefix `!`, slash commands also work)

| Command | Description |
|---|---|
| `/play <query or link>` | Play a song/playlist (YouTube, Spotify, SoundCloud) |
| `/pause` / `/resume` | Pause / resume |
| `/skip` | Skip current track |
| `/stop` | Stop and clear queue |
| `/queue [page]` | Show queue |
| `/nowplaying` | Show current track |
| `/volume <0-150>` | Set volume |
| `/leave` | Disconnect |
| `/welcome channel #ch` / `/welcome message <template>` | Configure welcome |
| `/goodbye channel #ch` / `/goodbye message <template>` | Configure goodbye |
| `/logs channel #ch` / `/logs enable` / `/logs disable` | Configure log channel mirroring |
| `/djrole @role` | Require a role for playback controls |
| `/prefix <new>` | Change text prefix for this server |
| `/settings` | Show current server configuration |
| `/ping` | Latency check |

Welcome/goodbye message placeholders: `{mention} {user} {tag} {guild} {member_count}`

---

## 6. Backup & migrating to a new host

Everything that matters lives in two places:

- `.env` — your secrets/config
- `data/bot.db` — all per-server settings (SQLite, single file)

To migrate: copy those two items (plus `logs/` if you want log history) to
the new host, then either `docker compose up -d --build` or repeat the
systemd steps above. No source code changes are required.

```bash
# quick backup
tar -czf bot-backup.tar.gz .env data/

# on the new host
tar -xzf bot-backup.tar.gz
```

---

## 7. Notes on Spotify playback

Spotify does not allow third-party bots to stream its proprietary audio.
This bot (like all stable "Spotify support" Discord bots) resolves Spotify
links/playlists to track metadata via Spotify's Web API, then plays the
matching audio from YouTube through Lavalink. If your Lavalink server has
the **LavaSrc** plugin configured (already set up in
`lavalink/application.yml`) with your Spotify credentials, this resolution
happens natively and efficiently; otherwise the bot falls back to using
`spotipy` directly plus a YouTube search per track.
