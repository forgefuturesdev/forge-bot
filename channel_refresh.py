#!/usr/bin/env python3
"""Plan, apply, verify or roll back the Forge public Discord refresh.

The refresh is intentionally additive. It creates a locked Education forum and
publishes versioned, pinned replacements in existing information channels. It
does not delete, rename or hide legacy channels or messages.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
import sys
from typing import Iterable

import requests

from newsroom import (
    DISCORD_BASE,
    DISCORD_TIMEOUT_SECONDS,
    FORGE_DISCORD_URL,
    FORGE_ICON_URL,
    FORGE_ORANGE,
    FORGE_SITE_URL,
    discord_headers,
)


TOKEN = os.environ.get("DISCORD_BOT_TOKEN", "")
GUILD_ID = os.environ.get("DISCORD_GUILD_ID", "1474405047679848643")
BOT_ID = os.environ.get("DISCORD_BOT_ID", "1482017269092716645")
EDUCATION_CATEGORY_ID = os.environ.get(
    "DISCORD_EDUCATION_CATEGORY_ID",
    "1482020931483471952",
)

CONTENT_VERSION = "2026.08.16"
CONTENT_MARKER = f"Forge public information | v{CONTENT_VERSION}"
FORUM_TOPIC = (
    f"{CONTENT_MARKER} | Platform rules and account guidance from Forge Futures."
)
FORUM_NAME = "forge-education"
LEGACY_FORUM_NAMES = ("education-hub",)

ASSET_DIR = Path(__file__).resolve().parent / "assets" / "education"
CHANNEL_NAMES = (
    "welcome",
    "faq",
    "platform-status",
    "rules-explained",
    "promotions",
    "links",
    "announcements",
    "daily-highlights",
    "market-watch",
    "get-roles",
    "open-ticket",
)

# Discord permission flags used for the education forum. Members can view,
# read and react, but only the bot and administrators can publish or reply.
ADD_REACTIONS = 1 << 6
VIEW_CHANNEL = 1 << 10
SEND_MESSAGES = 1 << 11
READ_MESSAGE_HISTORY = 1 << 16
CREATE_PUBLIC_THREADS = 1 << 35
CREATE_PRIVATE_THREADS = 1 << 36
SEND_MESSAGES_IN_THREADS = 1 << 38


class DiscordError(RuntimeError):
    """Raised for a failed Discord API mutation or required preflight."""


def request(
    method: str,
    path: str,
    *,
    json_body: dict | list | None = None,
    files: dict | None = None,
    reason: str | None = None,
) -> requests.Response:
    headers = discord_headers(TOKEN)
    if files:
        headers.pop("Content-Type", None)
    if reason:
        headers["X-Audit-Log-Reason"] = reason
    try:
        return requests.request(
            method,
            f"{DISCORD_BASE}{path}",
            headers=headers,
            json=json_body if not files else None,
            files=files,
            timeout=DISCORD_TIMEOUT_SECONDS,
        )
    except requests.RequestException as exc:
        raise DiscordError(f"Discord {method} {path} failed: {type(exc).__name__}") from exc


def expect(response: requests.Response, statuses: tuple[int, ...], label: str) -> dict:
    if response.status_code not in statuses:
        raise DiscordError(f"{label} failed with HTTP {response.status_code}")
    if response.status_code == 204:
        return {}
    return response.json()


def public_embed(
    title: str,
    description: str,
    *,
    fields: list[dict] | None = None,
    section: str = "PUBLIC INFORMATION",
    image_name: str | None = None,
) -> dict:
    embed = {
        "title": title,
        "description": description,
        "color": FORGE_ORANGE,
        "url": FORGE_SITE_URL,
        "author": {
            "name": f"FORGE FUTURES | {section}",
            "url": FORGE_SITE_URL,
            "icon_url": FORGE_ICON_URL,
        },
        "footer": {
            "text": (
                f"{CONTENT_MARKER} | Simulated accounts | "
                "Information only - not financial advice"
            ),
            "icon_url": FORGE_ICON_URL,
        },
    }
    if fields:
        embed["fields"] = fields
    if image_name:
        embed["image"] = {"url": f"attachment://{image_name}"}
    return embed


def validate_embed(embed: dict) -> None:
    if len(embed.get("title", "")) > 256:
        raise ValueError("Embed title exceeds Discord's 256-character limit")
    if len(embed.get("description", "")) > 4096:
        raise ValueError("Embed description exceeds Discord's 4096-character limit")
    fields = embed.get("fields", [])
    if len(fields) > 25:
        raise ValueError("Embed contains more than 25 fields")
    total = len(embed.get("title", "")) + len(embed.get("description", ""))
    total += len(embed.get("footer", {}).get("text", ""))
    total += len(embed.get("author", {}).get("name", ""))
    for field in fields:
        if len(field.get("name", "")) > 256 or len(field.get("value", "")) > 1024:
            raise ValueError("Embed field exceeds a Discord field limit")
        total += len(field.get("name", "")) + len(field.get("value", ""))
    if total > 6000:
        raise ValueError("Embed exceeds Discord's 6000-character total limit")


def validate_embeds(embeds: Iterable[dict]) -> None:
    embeds = list(embeds)
    if len(embeds) > 10:
        raise ValueError("Discord messages support at most 10 embeds")
    for embed in embeds:
        validate_embed(embed)


def mention(channels: dict[str, dict], name: str) -> str:
    channel = channels.get(name)
    return f"<#{channel['id']}>" if channel else f"#{name}"


def build_education_guides() -> list[dict]:
    return [
        {
            "name": "How Forge Works",
            "legacy_names": ("00-start-here-how-forge-works",),
            "tag": "Start Here",
            "asset": "education-hub.png",
            "embeds": [
                public_embed(
                    "How Forge Works",
                    (
                        "Forge Futures provides simulated futures evaluations and qualified "
                        "accounts. Orders are not sent to a live brokerage account or exchange. "
                        "Use this guide for the basics, then check the website rules and checkout "
                        "for the latest details."
                    ),
                    section="EDUCATION",
                    image_name="education-hub.png",
                    fields=[
                        {
                            "name": "Account Journey",
                            "value": (
                                "• Choose a Zero, Standard or Advanced evaluation.\n"
                                "• Trade the simulated account within its rules.\n"
                                "• Meet the pass conditions and complete KYC when required.\n"
                                "• Trade a simulated qualified account and request eligible payouts."
                            ),
                            "inline": False,
                        },
                        {
                            "name": "Supported Contracts",
                            "value": "ES, NQ, MES and MNQ.",
                            "inline": True,
                        },
                        {
                            "name": "Account Limits",
                            "value": (
                                "You can hold up to five qualified accounts per tier. Make at least "
                                "one trade every 10 trading days to keep each account active."
                            ),
                            "inline": True,
                        },
                        {
                            "name": "Quick Links",
                            "value": (
                                f"[Plans]({FORGE_SITE_URL}/plans) | "
                                f"[Rules]({FORGE_SITE_URL}/rules) | "
                                f"[Dashboard]({FORGE_SITE_URL}/app)"
                            ),
                            "inline": False,
                        },
                    ],
                )
            ],
        },
        {
            "name": "Platform Orders & Positions",
            "legacy_names": ("01-platform-orders-and-positions",),
            "tag": "Platform",
            "asset": "platform-execution.png",
            "embeds": [
                public_embed(
                    "Platform Orders & Positions",
                    (
                        "Before placing an order, confirm the account, contract, side, order type, "
                        "quantity and intended risk."
                    ),
                    section="EDUCATION",
                    image_name="platform-execution.png",
                    fields=[
                        {
                            "name": "Market Orders",
                            "value": (
                                "A market order requests the next available simulated fill. It "
                                "prioritises execution rather than a specific price."
                            ),
                            "inline": True,
                        },
                        {
                            "name": "Limit & Stop Orders",
                            "value": (
                                "A limit order waits for its selected price or better. A stop order "
                                "activates after its trigger price is reached. Check all working "
                                "orders after submission."
                            ),
                            "inline": True,
                        },
                        {
                            "name": "Before Sending",
                            "value": (
                                "Check account, symbol, side, order type, quantity and intended risk. "
                                "Hotkeys are shortcuts, not a substitute for those checks."
                            ),
                            "inline": False,
                        },
                        {
                            "name": "After Sending",
                            "value": (
                                "Confirm the order state, verify the resulting position and use the "
                                "platform controls to reduce or close risk deliberately."
                            ),
                            "inline": False,
                        },
                    ],
                )
            ],
        },
        {
            "name": "Risk Discipline & Account Guardrails",
            "legacy_names": ("02-risk-discipline-and-account-guardrails",),
            "tag": "Risk",
            "asset": "risk-discipline.png",
            "embeds": [
                public_embed(
                    "Risk Discipline & Account Guardrails",
                    (
                        "Account rules are limits, not targets. Set a personal stop inside the "
                        "published limit so one trade or session cannot breach the account."
                    ),
                    section="EDUCATION",
                    image_name="risk-discipline.png",
                    fields=[
                        {
                            "name": "Zero",
                            "value": (
                                "25K: $1,000 drawdown / $500 daily guard\n"
                                "50K: $2,000 drawdown / $1,000 daily guard\n"
                                "100K: $3,000 drawdown / $2,000 daily guard"
                            ),
                            "inline": True,
                        },
                        {
                            "name": "Standard",
                            "value": (
                                "50K: $2,000 drawdown\n"
                                "100K: $3,000 drawdown\n"
                                "150K: $4,500 drawdown\n"
                                "No daily loss guard."
                            ),
                            "inline": True,
                        },
                        {
                            "name": "Advanced",
                            "value": (
                                "50K: $1,750 drawdown\n"
                                "100K: $3,500 drawdown\n"
                                "150K: $5,250 drawdown\n"
                                "No daily loss guard."
                            ),
                            "inline": True,
                        },
                        {
                            "name": "A Consistent Session",
                            "value": (
                                "Set your risk before the session. Check scheduled news and market "
                                "conditions. Take only planned setups. Stop at your personal limit "
                                "and journal the result."
                            ),
                            "inline": False,
                        },
                    ],
                )
            ],
        },
        {
            "name": "Payout Readiness & Limits",
            "legacy_names": ("03-payout-readiness-and-limits",),
            "tag": "Payouts",
            "asset": "payout-readiness.png",
            "embeds": [
                public_embed(
                    "Payout Readiness & Limits",
                    (
                        "A qualified account needs five winning days with at least $200 net profit each. "
                        "Every request is limited to the lower of 50% of eligible account profit and "
                        "the applicable plan cap. The payout amount is deducted from the account when paid."
                    ),
                    section="EDUCATION",
                    image_name="payout-readiness.png",
                    fields=[
                        {
                            "name": "Minimum Request",
                            "value": "Zero $200 | Standard $500 | Advanced $1,000",
                            "inline": False,
                        },
                        {
                            "name": "Frequency & Profit Split",
                            "value": (
                                "Zero monthly | Standard bi-weekly | Advanced weekly\n"
                                "All tiers: trader receives 90% of the approved amount."
                            ),
                            "inline": False,
                        },
                        {
                            "name": "Zero Payout Caps",
                            "value": "25K $1,000 | 50K $1,500 | 100K $2,500",
                            "inline": False,
                        },
                        {
                            "name": "Standard Payout Ladder",
                            "value": (
                                "Caps rise after each paid payout.\n"
                                "50K: $2,000, $2,250, $2,500, $3,000, then $4,000\n"
                                "100K: $2,500, $3,000, $3,500, $4,000, then $5,000\n"
                                "150K: $3,000, $3,500, $4,000, $5,000, then $6,000"
                            ),
                            "inline": False,
                        },
                        {
                            "name": "Advanced Payout Cap",
                            "value": (
                                "$15,000 per request for every Advanced account size."
                            ),
                            "inline": False,
                        },
                        {
                            "name": "Processing Target",
                            "value": (
                                "Forge aims to review and process payout requests within 24 hours. "
                                "Arrival time after processing depends on the payment method and bank."
                            ),
                            "inline": False,
                        },
                    ],
                )
            ],
        },
        {
            "name": "Trader Process: Prepare, Execute, Review, Reset",
            "legacy_names": ("04-trader-process-prepare-execute-review-reset",),
            "tag": "Psychology",
            "asset": "trader-process.png",
            "embeds": [
                public_embed(
                    "Trader Process: Prepare, Execute, Review, Reset",
                    (
                        "Consistency comes from following a process, not forcing a daily result. "
                        "Use the same routine before, during and after every session."
                    ),
                    section="EDUCATION",
                    image_name="trader-process.png",
                    fields=[
                        {
                            "name": "Prepare",
                            "value": "Define the session window, key events, setup and maximum personal risk.",
                            "inline": True,
                        },
                        {
                            "name": "Execute",
                            "value": "Trade only the planned conditions and verify every order after sending it.",
                            "inline": True,
                        },
                        {
                            "name": "Review",
                            "value": "Record the decision, execution quality and whether the plan was followed.",
                            "inline": True,
                        },
                        {
                            "name": "Reset",
                            "value": (
                                "Close the session mentally. Do not increase size to recover a loss or "
                                "manufacture a qualifying day."
                            ),
                            "inline": True,
                        },
                    ],
                )
            ],
        },
    ]


def build_public_channel_embeds(channels: dict[str, dict]) -> dict[str, list[dict]]:
    return {
        "welcome": [
            public_embed(
                "WELCOME TO FORGE FUTURES | START HERE",
                (
                    "Forge Futures provides simulated futures evaluations and qualified accounts. "
                    "Use the current channels below to get set up without relying on older posts."
                ),
                fields=[
                    {
                        "name": "1 | READ",
                        "value": (
                            f"Start with {mention(channels, 'rules-explained')} and "
                            f"{mention(channels, FORUM_NAME)}."
                        ),
                        "inline": False,
                    },
                    {
                        "name": "2 | FOLLOW",
                        "value": (
                            f"Use {mention(channels, 'announcements')}, "
                            f"{mention(channels, 'daily-highlights')} and "
                            f"{mention(channels, 'market-watch')} for official updates."
                        ),
                        "inline": False,
                    },
                    {
                        "name": "3 | GET HELP",
                        "value": (
                            f"Check {mention(channels, 'faq')} or open {mention(channels, 'open-ticket')}. "
                            "Discord community access is available 24/7; live chat and email replies "
                            "are staffed 09:00-18:00 UK time."
                        ),
                        "inline": False,
                    },
                ],
            )
        ],
        "faq": [
            public_embed(
                "CURRENT FAQ | ACCOUNTS AND TRADING",
                "The short answers below reflect the current Forge rules and platform scope.",
                fields=[
                    {
                        "name": "ARE THE ACCOUNTS LIVE BROKERAGE ACCOUNTS?",
                        "value": "No. Evaluations, orders, fills and qualified accounts are simulated.",
                        "inline": False,
                    },
                    {
                        "name": "WHAT CAN I TRADE?",
                        "value": "ES, NQ, MES and MNQ.",
                        "inline": True,
                    },
                    {
                        "name": "MINIMUM EVALUATION DAYS",
                        "value": "Zero: 1 day | Standard and Advanced: 2 days.",
                        "inline": True,
                    },
                    {
                        "name": "CAN I RESET AN ACCOUNT?",
                        "value": (
                            "A breached evaluation can be reset for its published fee. Qualified or "
                            "funded-stage accounts cannot be reset. Zero has no activation fee; "
                            "Standard and Advanced activation is $99."
                        ),
                        "inline": False,
                    },
                    {
                        "name": "NEWS TRADING",
                        "value": (
                            "Evaluations are unrestricted. On a qualified Zero account, existing "
                            "positions may be held but no new position may be opened within two minutes "
                            "either side of a high-impact release. Standard and Advanced have no specific "
                            "news restriction."
                        ),
                        "inline": False,
                    },
                ],
            ),
            public_embed(
                "CURRENT FAQ | PAYOUTS AND SUPPORT",
                "Eligibility is checked against the account ledger and current rules before approval.",
                fields=[
                    {
                        "name": "PAYOUT READINESS",
                        "value": (
                            "Five winning days of at least $200 net profit each. Minimum request: "
                            "Zero $200, Standard $500, Advanced $1,000."
                        ),
                        "inline": False,
                    },
                    {
                        "name": "PAYOUT LIMIT / SPLIT",
                        "value": (
                            "Lower of 50% eligible account profit and the plan cap. The trader receives "
                            "90% of the approved request; the requested amount is deducted from the account."
                        ),
                        "inline": False,
                    },
                    {
                        "name": "PROCESSING TARGET",
                        "value": (
                            "Forge aims to review and process requests within 24 hours. Arrival after "
                            "processing depends on the payment method and banking network."
                        ),
                        "inline": False,
                    },
                    {
                        "name": "SUPPORT",
                        "value": (
                            "Discord community access is available 24/7. Live chat and email replies are "
                            "staffed 09:00-18:00 UK time. Email: support@forge-futures.com."
                        ),
                        "inline": False,
                    },
                ],
            ),
        ],
        "rules-explained": [
            public_embed(
                "CURRENT RULES | UNIVERSAL CONTROLS",
                (
                    "All orders and balances are simulated. Rule breaches are enforced by the account "
                    "ledger; staff review does not replace the published limits."
                ),
                fields=[
                    {
                        "name": "PROFIT SPLIT",
                        "value": "Flat 90% to the trader on all plans.",
                        "inline": True,
                    },
                    {
                        "name": "QUALIFYING DAYS",
                        "value": "Five winning days of at least $200 net profit each before payout.",
                        "inline": True,
                    },
                    {
                        "name": "PAYOUT LIMIT",
                        "value": "Lower of 50% eligible profit and the plan cap or ladder step.",
                        "inline": True,
                    },
                    {
                        "name": "INACTIVITY",
                        "value": "Place at least one trade every 10 trading days.",
                        "inline": True,
                    },
                    {
                        "name": "ACCOUNT LIMIT",
                        "value": "Up to five qualified accounts per tier.",
                        "inline": True,
                    },
                    {
                        "name": "OFFICIAL DETAIL",
                        "value": f"Always check [the current rules page]({FORGE_SITE_URL}/rules).",
                        "inline": False,
                    },
                ],
            ),
            public_embed(
                "CURRENT RULES | PLAN REFERENCE",
                "Evaluation consistency applies to Standard and Advanced only; Zero has no evaluation consistency rule.",
                fields=[
                    {
                        "name": "ZERO | 25K / 50K / 100K",
                        "value": (
                            "Drawdown: $1,000 / $2,000 / $3,000\n"
                            "Daily guard: $500 / $1,000 / $2,000\n"
                            "Qualified consistency: 40%\n"
                            "Payout caps: $1,000 / $1,500 / $2,500"
                        ),
                        "inline": False,
                    },
                    {
                        "name": "STANDARD | 50K / 100K / 150K",
                        "value": (
                            "Drawdown: $2,000 / $3,000 / $4,500\n"
                            "No daily loss guard | Evaluation consistency: 50%\n"
                            "Payout ladders: $2K->$4K / $2.5K->$5K / $3K->$6K"
                        ),
                        "inline": False,
                    },
                    {
                        "name": "ADVANCED | 50K / 100K / 150K",
                        "value": (
                            "Drawdown: $1,750 / $3,500 / $5,250\n"
                            "No daily loss guard | Evaluation consistency: 50%\n"
                            "Payout cap: $15,000 for every size"
                        ),
                        "inline": False,
                    },
                ],
            ),
        ],
        "promotions": [
            public_embed(
                "CURRENT OFFER | 20% OFF WITH FORGE",
                (
                    "Use code **FORGE** at checkout for 20% off eligible evaluation fees. The final "
                    "price shown in the verified Forge checkout is authoritative. Activation and reset "
                    "fees are excluded unless the checkout explicitly shows a discount."
                ),
                fields=[
                    {
                        "name": "USE THE OFFICIAL CHECKOUT",
                        "value": f"[View current plans]({FORGE_SITE_URL}/plans)",
                        "inline": False,
                    }
                ],
            )
        ],
        "platform-status": [
            public_embed(
                "PLATFORM STATUS | HOW UPDATES WORK",
                (
                    "This is the official Discord channel for confirmed incidents, maintenance and "
                    "recovery updates. This pinned guide does not claim the platform is healthy or "
                    "unhealthy; time-stamped staff notices below it provide the current position."
                ),
                fields=[
                    {
                        "name": "IF SOMETHING LOOKS WRONG",
                        "value": (
                            "Stop submitting repeat actions, refresh once, record the time and screenshot, "
                            f"then use {mention(channels, 'open-ticket')} or the Blaze live-chat button."
                        ),
                        "inline": False,
                    },
                    {
                        "name": "OFFICIAL UPDATE ORDER",
                        "value": (
                            f"Check {mention(channels, 'platform-status')} first, then "
                            f"{mention(channels, 'announcements')}. Do not rely on unofficial DMs."
                        ),
                        "inline": False,
                    },
                ],
            )
        ],
        "links": [
            public_embed(
                "OFFICIAL FORGE FUTURES LINKS",
                "Use these links to avoid impersonation, stale bookmarks and unofficial support contacts.",
                fields=[
                    {
                        "name": "WEBSITE",
                        "value": f"[forge-futures.com]({FORGE_SITE_URL})",
                        "inline": True,
                    },
                    {
                        "name": "PLANS",
                        "value": f"[Current plans]({FORGE_SITE_URL}/plans)",
                        "inline": True,
                    },
                    {
                        "name": "DASHBOARD",
                        "value": f"[Forge dashboard]({FORGE_SITE_URL}/app)",
                        "inline": True,
                    },
                    {
                        "name": "RULES",
                        "value": f"[Current rules]({FORGE_SITE_URL}/rules)",
                        "inline": True,
                    },
                    {
                        "name": "DISCORD",
                        "value": f"[Official community]({FORGE_DISCORD_URL})",
                        "inline": True,
                    },
                    {
                        "name": "SUPPORT",
                        "value": "support@forge-futures.com or the Blaze button on the website.",
                        "inline": False,
                    },
                    {
                        "name": "SECURITY",
                        "value": (
                            "Forge staff will not request your password, email password, MFA code, "
                            "recovery code or API secret in Discord."
                        ),
                        "inline": False,
                    },
                ],
            )
        ],
    }


def get_guild_channels() -> list[dict]:
    return expect(
        request("GET", f"/guilds/{GUILD_ID}/channels"),
        (200,),
        "Channel inventory",
    )


def channel_key(value: object) -> str:
    """Return the stable suffix used by Forge's emoji-decorated channels."""
    name = str(value or "").strip()
    if "┃" in name:
        name = name.rsplit("┃", 1)[1]
    return name.strip().casefold()


def index_channels(channel_list: list[dict]) -> dict[str, dict]:
    indexed = {str(channel.get("name")): channel for channel in channel_list}
    aliases: dict[str, dict] = {}
    collisions: set[str] = set()
    for channel in channel_list:
        alias = channel_key(channel.get("name"))
        if not alias:
            continue
        if alias in aliases and aliases[alias].get("id") != channel.get("id"):
            collisions.add(alias)
            continue
        aliases[alias] = channel
    indexed.update(
        (alias, channel)
        for alias, channel in aliases.items()
        if alias not in collisions
    )
    return indexed


def find_version_message(channel_id: str) -> str | None:
    messages = expect(
        request("GET", f"/channels/{channel_id}/messages?limit=100"),
        (200,),
        "Message inventory",
    )
    for message in messages:
        if str(message.get("author", {}).get("id")) != BOT_ID:
            continue
        for embed in message.get("embeds", []):
            if CONTENT_MARKER in embed.get("footer", {}).get("text", ""):
                return str(message.get("id"))
    return None


def post_and_pin(channel_id: str, embeds: list[dict]) -> str:
    validate_embeds(embeds)
    message = expect(
        request(
            "POST",
            f"/channels/{channel_id}/messages",
            json_body={"allowed_mentions": {"parse": []}, "embeds": embeds},
        ),
        (200, 201),
        "Current information post",
    )
    message_id = str(message["id"])
    expect(
        request(
            "PUT",
            f"/channels/{channel_id}/messages/pins/{message_id}",
            reason=f"Pin {CONTENT_MARKER}",
        ),
        (200, 204),
        "Current information pin",
    )
    return message_id


def desired_forum_payload() -> dict:
    member_allow = VIEW_CHANNEL | READ_MESSAGE_HISTORY | ADD_REACTIONS
    member_deny = SEND_MESSAGES | CREATE_PUBLIC_THREADS | CREATE_PRIVATE_THREADS | SEND_MESSAGES_IN_THREADS
    bot_allow = member_allow | SEND_MESSAGES | CREATE_PUBLIC_THREADS | CREATE_PRIVATE_THREADS | SEND_MESSAGES_IN_THREADS
    return {
        "name": FORUM_NAME,
        "type": 15,
        "parent_id": EDUCATION_CATEGORY_ID,
        "topic": FORUM_TOPIC,
        "default_auto_archive_duration": 10080,
        "default_forum_layout": 2,
        "default_sort_order": 0,
        "available_tags": [
            {"name": "Start Here", "moderated": False, "emoji_name": "🧭"},
            {"name": "Platform", "moderated": False, "emoji_name": "🖥️"},
            {"name": "Risk", "moderated": False, "emoji_name": "🛡️"},
            {"name": "Payouts", "moderated": False, "emoji_name": "✅"},
            {"name": "Psychology", "moderated": False, "emoji_name": "🧠"},
        ],
        "permission_overwrites": [
            {
                "id": GUILD_ID,
                "type": 0,
                "allow": str(member_allow),
                "deny": str(member_deny),
            },
            {
                "id": BOT_ID,
                "type": 1,
                "allow": str(bot_allow),
                "deny": "0",
            },
        ],
    }


def ensure_forum(channels: dict[str, dict]) -> dict:
    existing = channels.get(FORUM_NAME)
    if not existing:
        existing = next(
            (channels.get(name) for name in LEGACY_FORUM_NAMES if channels.get(name)),
            None,
        )
    if existing:
        if existing.get("type") != 15 or existing.get("parent_id") != EDUCATION_CATEGORY_ID:
            raise DiscordError("Existing Forge Education channel has an unexpected type or category")
        if CONTENT_MARKER not in str(existing.get("topic") or ""):
            raise DiscordError("Existing Forge Education channel is missing its managed marker")
        if existing.get("name") != FORUM_NAME or existing.get("topic") != FORUM_TOPIC:
            existing = expect(
                request(
                    "PATCH",
                    f"/channels/{existing['id']}",
                    json_body={"name": FORUM_NAME, "topic": FORUM_TOPIC},
                    reason=f"Rename {CONTENT_MARKER} forum to Forge Education",
                ),
                (200,),
                "Forge Education forum rename",
            )
        return existing
    return expect(
        request(
            "POST",
            f"/guilds/{GUILD_ID}/channels",
            json_body=desired_forum_payload(),
            reason=f"Create {CONTENT_MARKER} Education hub",
        ),
        (200, 201),
        "Education forum creation",
    )


def active_and_archived_threads(forum_id: str) -> list[dict]:
    active = expect(
        request("GET", f"/guilds/{GUILD_ID}/threads/active"),
        (200,),
        "Active thread inventory",
    ).get("threads", [])
    archived = expect(
        request("GET", f"/channels/{forum_id}/threads/archived/public?limit=100"),
        (200,),
        "Archived thread inventory",
    ).get("threads", [])
    return [thread for thread in active + archived if thread.get("parent_id") == forum_id]


def guide_attachment_name(guide: dict, prefix: str = "forge-education") -> str:
    return str(guide.get("attachment_name") or f"{prefix}-{guide['asset']}")


def embeds_for_attachment(guide: dict, attachment_name: str) -> list[dict]:
    embeds = json.loads(json.dumps(guide["embeds"]))
    for embed in embeds:
        # Discord renders an uploaded image attachment on its own. Binding the
        # same file as a rich-embed image makes forum gallery cards show it
        # twice, so the managed message carries one attachment and text-only
        # rich embeds.
        embed.pop("image", None)
    return embeds


def create_forum_guide(
    forum: dict,
    guide: dict,
    *,
    asset_dir: Path = ASSET_DIR,
    attachment_prefix: str = "forge-education",
    label: str = "Education",
) -> str:
    asset_path = asset_dir / guide["asset"]
    if not asset_path.is_file():
        raise DiscordError(f"Missing {label} asset: {asset_path.name}")
    validate_embeds(guide["embeds"])
    attachment_name = guide_attachment_name(guide, attachment_prefix)
    desired_embeds = embeds_for_attachment(guide, attachment_name)
    tag_ids = {
        str(tag.get("name")): str(tag.get("id"))
        for tag in forum.get("available_tags", [])
    }
    tag_id = tag_ids.get(guide["tag"])
    if not tag_id:
        raise DiscordError(f"Education forum is missing tag: {guide['tag']}")
    payload = {
        "name": guide["name"],
        "auto_archive_duration": 10080,
        "applied_tags": [tag_id],
        "message": {
            "allowed_mentions": {"parse": []},
            "embeds": desired_embeds,
            "attachments": [{"id": 0, "filename": attachment_name}],
        },
    }
    with asset_path.open("rb") as asset_file:
        result = expect(
            request(
                "POST",
                f"/channels/{forum['id']}/threads",
                files={
                    "payload_json": (None, json.dumps(payload), "application/json"),
                    "files[0]": (attachment_name, asset_file, "image/png"),
                },
                reason=f"Publish {CONTENT_MARKER} Education guide",
            ),
            (200, 201),
            f"{label} guide {guide['name']}",
        )
    return str(result["id"])


def find_guide_thread(existing_threads: dict[str, dict], guide: dict) -> dict | None:
    thread = existing_threads.get(guide["name"])
    if thread:
        return thread
    for legacy_name in guide.get("legacy_names", ()):
        thread = existing_threads.get(legacy_name)
        if thread:
            return thread
    return None


def embed_copy_signature(embeds: Iterable[dict]) -> list[dict]:
    """Return only the public copy fields that Discord preserves verbatim."""
    return [
        {
            "title": embed.get("title"),
            "description": embed.get("description"),
            "fields": [
                {
                    "name": field.get("name"),
                    "value": field.get("value"),
                    "inline": bool(field.get("inline", False)),
                }
                for field in embed.get("fields", [])
            ],
        }
        for embed in embeds
    ]


def update_forum_guide(
    thread: dict,
    guide: dict,
    *,
    asset_dir: Path = ASSET_DIR,
    attachment_prefix: str = "forge-education",
    label: str = "Education",
) -> None:
    """Rename and refresh one managed guide with exactly one bound artwork file."""
    thread_id = str(thread["id"])
    current_message = expect(
        request("GET", f"/channels/{thread_id}/messages/{thread_id}"),
        (200,),
        f"{label} guide inventory {guide['name']}",
    )
    asset_path = asset_dir / guide["asset"]
    if not asset_path.is_file():
        raise DiscordError(f"Missing {label} asset: {asset_path.name}")
    attachment_name = guide_attachment_name(guide, attachment_prefix)
    desired_embeds = embeds_for_attachment(guide, attachment_name)
    current_embeds = current_message.get("embeds", [])
    current_attachments = current_message.get("attachments", [])
    artwork_is_current = (
        len(current_attachments) == 1
        and str(current_attachments[0].get("filename")) == attachment_name
    )
    layout_is_current = not any(
        embed.get("title") and embed.get("image")
        for embed in current_embeds
    )

    if str(thread.get("name")) != guide["name"]:
        expect(
            request(
                "PATCH",
                f"/channels/{thread_id}",
                json_body={"name": guide["name"]},
                reason=f"Rename {CONTENT_MARKER} Education guide",
            ),
            (200,),
            f"{label} guide rename {guide['name']}",
        )

    copy_is_current = embed_copy_signature(current_embeds) == embed_copy_signature(desired_embeds)
    if not copy_is_current or not artwork_is_current or not layout_is_current:
        payload = {
            "allowed_mentions": {"parse": []},
            "embeds": desired_embeds,
            "attachments": [{"id": 0, "filename": attachment_name}],
        }
        with asset_path.open("rb") as asset_file:
            expect(
                request(
                    "PATCH",
                    f"/channels/{thread_id}/messages/{thread_id}",
                    files={
                        "payload_json": (None, json.dumps(payload), "application/json"),
                        "files[0]": (attachment_name, asset_file, "image/png"),
                    },
                    reason=f"Refresh {CONTENT_MARKER} {label} guide",
                ),
                (200,),
                f"{label} guide update {guide['name']}",
            )


def verify_assets() -> None:
    for guide in build_education_guides():
        asset_path = ASSET_DIR / guide["asset"]
        if not asset_path.is_file() or asset_path.stat().st_size <= 0:
            raise DiscordError(f"Missing Education asset: {asset_path.name}")


def plan() -> None:
    verify_assets()
    channels = index_channels(get_guild_channels())
    missing = [name for name in CHANNEL_NAMES if name not in channels]
    if missing:
        raise DiscordError(f"Missing required channels: {', '.join(missing)}")
    forum = channels.get(FORUM_NAME) or next(
        (channels.get(name) for name in LEGACY_FORUM_NAMES if channels.get(name)),
        None,
    )
    forum_state = "exists" if forum else "will be created"
    existing_threads = {
        str(thread.get("name")): thread
        for thread in active_and_archived_threads(str(forum["id"]))
    } if forum else {}
    print(f"OK: guild {GUILD_ID}")
    print(f"PLAN: #{FORUM_NAME} {forum_state} under Education")
    for guide in build_education_guides():
        thread = find_guide_thread(existing_threads, guide)
        if not thread:
            state = "will be created"
        elif str(thread.get("name")) != guide["name"]:
            state = f"will be renamed from {thread.get('name')} and refreshed"
        else:
            state = "will be checked and refreshed if needed"
        print(f"PLAN: forum guide {guide['name']} [{guide['tag']}] {state}")
    for channel_name in build_public_channel_embeds(channels):
        channel_id = str(channels[channel_name]["id"])
        state = "already current" if find_version_message(channel_id) else "will receive a pinned current post"
        print(f"PLAN: #{channel_name} {state}")
    print("SAFE: no legacy message or channel will be deleted, renamed or hidden")


def apply() -> None:
    verify_assets()
    channels = index_channels(get_guild_channels())
    missing = [name for name in CHANNEL_NAMES if name not in channels]
    if missing:
        raise DiscordError(f"Missing required channels: {', '.join(missing)}")

    forum = ensure_forum(channels)
    channels[FORUM_NAME] = forum
    existing_threads = {
        str(thread.get("name")): thread
        for thread in active_and_archived_threads(str(forum["id"]))
    }
    # Create in reverse so Start Here is the most recent item in gallery view.
    for guide in reversed(build_education_guides()):
        thread = find_guide_thread(existing_threads, guide)
        if thread:
            old_name = str(thread.get("name"))
            update_forum_guide(thread, guide)
            if old_name == guide["name"]:
                print(f"CHECKED: forum guide {guide['name']}")
            else:
                print(f"RENAMED: forum guide {old_name} -> {guide['name']}")
            continue
        thread_id = create_forum_guide(forum, guide)
        print(f"CREATED: forum guide {guide['name']} ({thread_id})")

    for channel_name, embeds in build_public_channel_embeds(channels).items():
        channel_id = str(channels[channel_name]["id"])
        existing_message_id = find_version_message(channel_id)
        if existing_message_id:
            print(f"SKIP: #{channel_name} already current ({existing_message_id})")
            continue
        message_id = post_and_pin(channel_id, embeds)
        print(f"CREATED: #{channel_name} current pinned post ({message_id})")

    print(f"OK: {CONTENT_MARKER} applied without modifying legacy content")


def verify() -> None:
    channels = index_channels(get_guild_channels())
    forum = channels.get(FORUM_NAME)
    if not forum or CONTENT_MARKER not in str(forum.get("topic") or ""):
        raise DiscordError("Managed Education forum is missing")
    threads = {
        str(thread.get("name")): thread
        for thread in active_and_archived_threads(str(forum["id"]))
    }
    missing_threads = [guide["name"] for guide in build_education_guides() if guide["name"] not in threads]
    if missing_threads:
        raise DiscordError(f"Missing Education guides: {', '.join(missing_threads)}")
    for guide in build_education_guides():
        thread_id = str(threads[guide["name"]]["id"])
        message = expect(
            request("GET", f"/channels/{thread_id}/messages/{thread_id}"),
            (200,),
            f"Education guide verification {guide['name']}",
        )
        if embed_copy_signature(message.get("embeds", [])) != embed_copy_signature(guide["embeds"]):
            raise DiscordError(f"Education guide copy is stale: {guide['name']}")
        attachments = message.get("attachments", [])
        expected_filename = guide_attachment_name(guide)
        rich_image_embeds = [
            embed
            for embed in message.get("embeds", [])
            if embed.get("title") and embed.get("image", {}).get("url")
        ]
        if rich_image_embeds or len(attachments) != 1:
            raise DiscordError(f"Education guide must show exactly one image: {guide['name']}")
        if str(attachments[0].get("filename")) != expected_filename:
            raise DiscordError(f"Education guide artwork is stale: {guide['name']}")
    for channel_name in build_public_channel_embeds(channels):
        channel = channels.get(channel_name)
        if not channel or not find_version_message(str(channel["id"])):
            raise DiscordError(f"Missing current post in #{channel_name}")
    print("OK: Forge Education, five guides and six current pinned channel posts verified")


def rollback() -> None:
    channels = index_channels(get_guild_channels())
    for channel_name in build_public_channel_embeds(channels):
        channel = channels.get(channel_name)
        if not channel:
            continue
        message_id = find_version_message(str(channel["id"]))
        if not message_id:
            continue
        expect(
            request(
                "DELETE",
                f"/channels/{channel['id']}/messages/{message_id}",
                reason=f"Roll back {CONTENT_MARKER}",
            ),
            (200, 204),
            f"Rollback #{channel_name}",
        )
        print(f"REMOVED: managed post from #{channel_name}")
    forum = channels.get(FORUM_NAME)
    if forum and CONTENT_MARKER in str(forum.get("topic") or ""):
        expect(
            request(
                "DELETE",
                f"/channels/{forum['id']}",
                reason=f"Roll back {CONTENT_MARKER}",
            ),
            (200, 204),
            "Education forum rollback",
        )
        print(f"REMOVED: managed #{FORUM_NAME} forum")
    print("OK: refresh rollback completed; legacy content was untouched")


def main() -> None:
    mode = sys.argv[1] if len(sys.argv) > 1 else "plan"
    if mode not in {"plan", "apply", "verify", "rollback"}:
        raise SystemExit("Usage: python channel_refresh.py [plan|apply|verify|rollback]")
    if not TOKEN:
        raise SystemExit("DISCORD_BOT_TOKEN is required")
    try:
        {"plan": plan, "apply": apply, "verify": verify, "rollback": rollback}[mode]()
    except (DiscordError, ValueError) as exc:
        print(f"ERROR: {exc}")
        raise SystemExit(1) from exc


if __name__ == "__main__":
    main()
