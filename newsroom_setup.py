#!/usr/bin/env python3
"""Check the Forge newsroom channels and publish the reusable follow guide."""

import os
import sys

import requests

from newsroom import (
    DISCORD_BASE,
    DISCORD_TIMEOUT_SECONDS,
    FORGE_DISCORD_URL,
    FORGE_ORANGE,
    FORGE_SITE_URL,
    brand_embed,
    discord_headers,
    post_discord,
)


TOKEN = os.environ["DISCORD_BOT_TOKEN"]
CHANNELS = {
    "daily-highlights": os.environ.get(
        "DISCORD_DAILY_HIGHLIGHTS_CHANNEL_ID",
        "1482427993140760636",
    ),
    "market-watch": os.environ.get(
        "DISCORD_MARKET_WATCH_CHANNEL_ID",
        "1482020924298362912",
    ),
    "announcements": os.environ.get(
        "DISCORD_ANNOUNCEMENTS_CHANNEL_ID",
        "1482020877146263594",
    ),
}
GUIDE_TITLE = "📣 FOLLOW FORGE MARKET DESK IN YOUR SERVER"


def get_channel(channel_id: str) -> dict | None:
    try:
        response = requests.get(
            f"{DISCORD_BASE}/channels/{channel_id}",
            headers=discord_headers(TOKEN),
            timeout=DISCORD_TIMEOUT_SECONDS,
        )
    except requests.RequestException:
        return None
    return response.json() if response.status_code == 200 else None


def find_guide(channel_id: str) -> str | None:
    try:
        response = requests.get(
            f"{DISCORD_BASE}/channels/{channel_id}/messages?limit=50",
            headers=discord_headers(TOKEN),
            timeout=DISCORD_TIMEOUT_SECONDS,
        )
    except requests.RequestException:
        return None
    if response.status_code != 200:
        return None
    for message in response.json():
        if any(embed.get("title") == GUIDE_TITLE for embed in message.get("embeds", [])):
            return str(message.get("id") or "") or None
    return None


def pin_message(channel_id: str, message_id: str) -> bool:
    try:
        response = requests.put(
            f"{DISCORD_BASE}/channels/{channel_id}/messages/pins/{message_id}",
            headers={
                **discord_headers(TOKEN),
                "X-Audit-Log-Reason": "Pin Forge Market Desk follow guide",
            },
            timeout=DISCORD_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        print(f"Guide pin failed: {type(exc).__name__}")
        return False
    if response.status_code not in (200, 204):
        print(f"Guide pin failed with HTTP {response.status_code}")
        return False
    return True


def build_follow_guide() -> dict:
    return brand_embed(
        {
            "title": GUIDE_TITLE,
            "description": (
                "Bring the curated Forge Futures Market Desk updates into a Discord "
                "server you manage."
            ),
            "color": FORGE_ORANGE,
            "fields": [
                {
                    "name": "HOW TO FOLLOW",
                    "value": (
                        "1. Select **Follow** at the top of this Announcement channel.\n"
                        "2. Choose the server and channel that should receive updates.\n"
                        "3. Discord will deliver each published Forge briefing automatically."
                    ),
                    "inline": False,
                },
                {
                    "name": "FORGE LINKS",
                    "value": (
                        f"[Visit Forge Futures]({FORGE_SITE_URL}) · "
                        f"[Join the community]({FORGE_DISCORD_URL})"
                    ),
                    "inline": False,
                },
            ],
        },
        data_note="Published briefings remain source-linked",
    )


def ensure_follow_guide(channel_id: str) -> bool:
    message_id = find_guide(channel_id)
    if not message_id:
        result = post_discord(TOKEN, channel_id, [build_follow_guide()], publish=False)
        if not result or not result.message_id:
            return False
        message_id = result.message_id
    return pin_message(channel_id, message_id)


def check_channels() -> bool:
    healthy = True
    for label, channel_id in CHANNELS.items():
        channel = get_channel(channel_id)
        if not channel:
            print(f"ERROR: {label}: unavailable")
            healthy = False
            continue
        channel_type = channel.get("type")
        status = "announcement" if channel_type == 5 else f"type {channel_type}"
        prefix = "OK" if channel_type == 5 else "ERROR"
        print(f"{prefix}: {label}: {status}")
        healthy = healthy and channel_type == 5
    return healthy


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "check"
    if not check_channels():
        raise SystemExit(1)
    if mode == "check":
        return
    if mode != "publish-guide":
        print(f"Unknown setup mode: {mode}")
        raise SystemExit(2)

    failures = [
        label
        for label in ("daily-highlights", "announcements")
        if not ensure_follow_guide(CHANNELS[label])
    ]
    if failures:
        print(f"Follow guide failed for: {', '.join(failures)}")
        raise SystemExit(1)
    print("OK: Forge Market Desk follow guides are pinned")


if __name__ == "__main__":
    main()
