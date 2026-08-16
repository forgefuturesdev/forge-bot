# Forge Futures Discord Bot

Deploy this repo to Railway.

## Required Railway Variables
- DISCORD_BOT_TOKEN
- DISCORD_GUILD_ID
- DISCORD_BOT_ID

The reporting service additionally requires `TELEGRAM_BOT_TOKEN` and
`TELEGRAM_CHAT_ID`.

The newsroom services use these optional explicit channel and brand settings:

- `DISCORD_DAILY_HIGHLIGHTS_CHANNEL_ID`
- `DISCORD_MARKET_WATCH_CHANNEL_ID`
- `DISCORD_ANNOUNCEMENTS_CHANNEL_ID`
- `FORGE_SITE_URL`, `FORGE_DISCORD_INVITE_URL` and `FORGE_ICON_URL`

## Discord application settings

Enable only the **Server Members Intent** and **Message Content Intent**.
Direct-message events are intentionally not subscribed to or processed.

The bot needs the following server permissions for its existing features:

- View Channels, Read Message History, Send Messages and Embed Links
- Attach Files, Add Reactions, Manage Messages and Pin Messages
- Create Private Threads, Send Messages in Threads and Manage Threads
- Manage Roles, Moderate Members, Kick Members and Manage Server

Do not grant the bot the Discord `Administrator` permission.

## Safety invariants

- Only events whose `guild_id` matches `DISCORD_GUILD_ID` are processed.
- Ticket replies are reposted before the original is removed. If reposting or
  attachment copying fails, the original message remains visible.
- Staff ticket attribution is retained privately in the moderation log.
- Automated briefings describe feed results and never declare a session safe
  to trade or invent support/resistance levels.
- Externally sourced titles are cleaned, source-linked and sent with mentions
  disabled. Quotes and calendars are explicitly described as potentially
  delayed, stale or incomplete.
- The session briefings and weekly outlook are published from Discord
  Announcement channels so other communities can follow them. The higher-
  frequency Market Watch feed remains internal to avoid follower spam.
- A failed Discord post or crosspost exits non-zero so Railway no longer marks
  a failed newsroom run as successful.

## Forge Market Desk

The deployed newsroom schedule runs:

- London, New York and Asia session briefings on weekdays
- a weekday economic-calendar digest
- three weekday Market Pulse checks, with cross-run link deduplication
- a published weekly outlook on Sunday

London and New York jobs use two UTC cron windows plus an in-process local-time
guard. This preserves a 07:30 London briefing and 09:00 New York briefing when
the UK or US changes daylight-saving time. The Asia briefing similarly stays at
23:30 UK time. Manual validation can bypass the guard with `--force`.

Run the read-only channel preflight before deploying or changing channel IDs:

```bash
python newsroom_setup.py check
```

The three configured newsroom channels must be Discord Announcement channels
(channel type 5). After validation, publish and pin the member-facing follow
guide once with:

```bash
python newsroom_setup.py publish-guide
```

Every outward-facing embed carries the Forge Futures Market Desk author mark,
Forge icon, website, source links and information-only disclaimer. The bot
avatar is managed through the Discord application profile and remains a clean
Blaze avatar without additional text or stamps.

## Public information and Education refresh

`channel_refresh.py` manages a versioned, information-only Education forum plus
current pinned posts in Welcome, FAQ, Rules Explained, Promotions, Platform
Status and Links. The operation preserves legacy messages and channels. Its
five managed Education guides can be renamed and copy-refreshed in place
without creating duplicates.

Run the read-only live plan first:

```bash
python channel_refresh.py plan
```

Apply and verify the refresh only after reviewing that plan:

```bash
python channel_refresh.py apply
python channel_refresh.py verify
```

The matching rollback removes only messages and the forum carrying this
release's managed marker. It does not touch legacy content:

```bash
python channel_refresh.py rollback
```

## Validation

```bash
python -m unittest discover -s tests -v
python -m compileall -q .
```
