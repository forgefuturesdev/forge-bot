# Forge Futures Discord Bot

Deploy this repo to Railway.

## Required Railway Variables
- DISCORD_BOT_TOKEN
- DISCORD_GUILD_ID
- DISCORD_BOT_ID

The reporting service additionally requires `TELEGRAM_BOT_TOKEN` and
`TELEGRAM_CHAT_ID`.

## Discord application settings

Enable only the **Server Members Intent** and **Message Content Intent**.
Direct-message events are intentionally not subscribed to or processed.

The bot needs the following server permissions for its existing features:

- View Channels, Read Message History, Send Messages and Embed Links
- Attach Files, Add Reactions and Manage Messages
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

## Validation

```bash
python -m unittest discover -s tests -v
python -m compileall -q .
```
